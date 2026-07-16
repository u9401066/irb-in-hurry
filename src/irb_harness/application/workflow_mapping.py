"""Upsert human-defined workflow transitions from verified evidence spans."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from irb_harness.application.evidence_mapping import (
    verify_evidence_selection,
    write_contract_mapping,
)
from irb_harness.domain.contracts import OrganizationContract


class WorkflowMappingError(ValueError):
    """Raised when a reviewed workflow definition cannot be applied safely."""


@dataclass(frozen=True)
class WorkflowMappingResult:
    contract_path: Path
    transition_event: str
    source_document_id: str
    span_ids: tuple[str, ...]
    states_added: tuple[str, ...]
    definition_sha256: str
    evidence_manifest_sha256: str


def map_workflow_from_evidence(
    contract_mapping: Mapping[str, Any],
    *,
    transition_definition: Mapping[str, Any],
    evidence_manifest_path: str | Path,
    source_document_id: str,
    span_ids: Iterable[str],
    output_path: str | Path,
    locator_hint: str | None = None,
    cache_root: str | Path = ".irb-source-cache",
    replace_transition: bool = False,
    update_output: bool = False,
) -> WorkflowMappingResult:
    """Upsert one explicit transition after verifying human-selected evidence."""
    original = deepcopy(dict(contract_mapping))
    contract = OrganizationContract.from_mapping(original)
    selection = verify_evidence_selection(
        contract,
        evidence_manifest_path=evidence_manifest_path,
        source_document_id=source_document_id,
        span_ids=span_ids,
    )
    definition = deepcopy(dict(transition_definition))
    event = definition.get("event")
    if not isinstance(event, str) or not event.strip():
        raise WorkflowMappingError("workflow definition must include a non-empty event")
    event = event.strip()
    definition["event"] = event
    definition.pop("evidence_refs", None)
    definition_sha256 = hashlib.sha256(
        json.dumps(
            definition, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()

    workflow = original.setdefault("workflow", {})
    if not isinstance(workflow, dict):
        raise WorkflowMappingError("contract workflow must be a mapping")
    states = workflow.setdefault("states", [])
    transitions = workflow.setdefault("transitions", [])
    if not isinstance(states, list) or not all(
        isinstance(item, str) for item in states
    ):
        raise WorkflowMappingError("workflow states must be a list of strings")
    if not isinstance(transitions, list):
        raise WorkflowMappingError("workflow transitions must be a list")
    matches = [
        item
        for item in transitions
        if isinstance(item, dict) and item.get("event") == event
    ]
    if len(matches) > 1:
        raise WorkflowMappingError(f"workflow event exists more than once: {event}")
    if matches and not replace_transition:
        raise WorkflowMappingError(
            f"workflow event already exists; use replace_transition explicitly: {event}"
        )

    if matches:
        previous = matches[0]
        references = deepcopy(previous.get("evidence_refs", []))
        entry = {**previous, **definition}
    else:
        references = []
        entry = definition
    if not isinstance(references, list):
        raise WorkflowMappingError("workflow evidence_refs must be a list")
    references = [
        item
        for item in references
        if not (
            isinstance(item, Mapping)
            and item.get("source_document_id") == source_document_id
        )
    ]
    reference: dict[str, Any] = {
        "source_document_id": source_document_id,
        "locator_status": "verified",
        "span_ids": list(selection.span_ids),
    }
    if locator_hint:
        reference["locator_hint"] = locator_hint
    references.append(reference)
    entry["evidence_refs"] = references

    declared_states = _declared_states(entry)
    states_added = tuple(state for state in declared_states if state not in states)
    states.extend(states_added)
    if matches:
        transitions[transitions.index(matches[0])] = entry
    else:
        transitions.append(entry)

    bindings = original.setdefault("evidence_bindings", [])
    if not isinstance(bindings, list):
        raise WorkflowMappingError("contract evidence_bindings must be a list")
    bindings[:] = [
        item
        for item in bindings
        if not (
            isinstance(item, Mapping)
            and (
                (
                    item.get("claim_type") == "workflow_transition"
                    and item.get("claim_id") == event
                )
                or item.get("transition_event") == event
            )
            and item.get("source_document_id") == source_document_id
        )
    ]
    bindings.append(selection.binding(claim_type="workflow_transition", claim_id=event))

    decisions = original.setdefault("review_decisions", [])
    if not isinstance(decisions, list):
        raise WorkflowMappingError("contract review_decisions must be a list")
    decisions[:] = [
        item
        for item in decisions
        if not (
            isinstance(item, Mapping)
            and item.get("decision_type") == "workflow_transition_upsert"
            and item.get("event") == event
            and item.get("source_document_id") == source_document_id
        )
    ]
    decisions.append(
        {
            "decision_type": "workflow_transition_upsert",
            "event": event,
            "source_document_id": source_document_id,
            "definition_sha256": definition_sha256,
            "evidence_manifest_sha256": selection.evidence_manifest_sha256,
            "span_ids": list(selection.span_ids),
            "states_added": list(states_added),
            "automated_rule_inference": False,
        }
    )

    OrganizationContract.from_mapping(original)
    target = Path(output_path).expanduser().resolve()
    write_contract_mapping(
        original,
        target,
        cache_root=cache_root,
        organization_id=contract.organization_id,
        update_output=update_output,
    )
    return WorkflowMappingResult(
        contract_path=target,
        transition_event=event,
        source_document_id=source_document_id,
        span_ids=selection.span_ids,
        states_added=states_added,
        definition_sha256=definition_sha256,
        evidence_manifest_sha256=selection.evidence_manifest_sha256,
    )


def _declared_states(transition: Mapping[str, Any]) -> tuple[str, ...]:
    raw_from = transition.get("from")
    if isinstance(raw_from, str):
        from_states = (raw_from,)
    elif isinstance(raw_from, list) and all(isinstance(item, str) for item in raw_from):
        from_states = tuple(raw_from)
    else:
        raise WorkflowMappingError(
            "workflow definition 'from' must be a string or list of strings"
        )
    to_state = transition.get("to")
    if not isinstance(to_state, str) or not to_state:
        raise WorkflowMappingError(
            "workflow definition must include a non-empty 'to' state"
        )
    return tuple(dict.fromkeys((*from_states, to_state)))
