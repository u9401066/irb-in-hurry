"""Map human-reviewed evidence spans into institutional contract requirements."""

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


class RequirementMappingError(ValueError):
    """Raised when a reviewed requirement cannot be safely applied."""


@dataclass(frozen=True)
class RequirementMappingResult:
    contract_path: Path
    requirement_id: str
    requirement_status: str
    source_document_id: str
    span_ids: tuple[str, ...]
    definition_sha256: str
    evidence_manifest_sha256: str


def map_requirement_from_evidence(
    contract_mapping: Mapping[str, Any],
    *,
    requirement_definition: Mapping[str, Any],
    evidence_manifest_path: str | Path,
    source_document_id: str,
    span_ids: Iterable[str],
    output_path: str | Path,
    locator_hint: str | None = None,
    cache_root: str | Path = ".irb-source-cache",
    replace_requirement: bool = False,
    update_output: bool = False,
) -> RequirementMappingResult:
    """Upsert one explicit requirement after verifying user-selected evidence spans."""
    original = deepcopy(dict(contract_mapping))
    contract = OrganizationContract.from_mapping(original)
    selection = verify_evidence_selection(
        contract,
        evidence_manifest_path=evidence_manifest_path,
        source_document_id=source_document_id,
        span_ids=span_ids,
    )
    definition = deepcopy(dict(requirement_definition))
    requirement_id = definition.get("requirement_id")
    if not isinstance(requirement_id, str) or not requirement_id:
        raise RequirementMappingError(
            "requirement definition must include a non-empty requirement_id"
        )
    definition.pop("status", None)
    definition.pop("evidence_refs", None)
    definition_sha256 = hashlib.sha256(
        json.dumps(
            definition, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()

    requirements = original.setdefault("requirements", [])
    if not isinstance(requirements, list):
        raise RequirementMappingError("contract requirements must be a list")
    matches = [
        item
        for item in requirements
        if isinstance(item, dict) and item.get("requirement_id") == requirement_id
    ]
    if len(matches) > 1:
        raise RequirementMappingError(
            f"requirement exists more than once: {requirement_id}"
        )
    if matches and not replace_requirement:
        raise RequirementMappingError(
            f"requirement already exists; use replace_requirement explicitly: {requirement_id}"
        )

    if matches:
        previous = matches[0]
        references = deepcopy(previous.get("evidence_refs", []))
        entry = {**previous, **definition}
    else:
        references = []
        entry = definition
    if not isinstance(references, list):
        raise RequirementMappingError("requirement evidence_refs must be a list")
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
    entry["status"] = (
        "verified"
        if references
        and all(
            isinstance(item, Mapping) and item.get("locator_status") == "verified"
            for item in references
        )
        else "needs_evidence"
    )

    if matches:
        requirements[requirements.index(matches[0])] = entry
    else:
        requirements.append(entry)

    bindings = original.setdefault("evidence_bindings", [])
    if not isinstance(bindings, list):
        raise RequirementMappingError("contract evidence_bindings must be a list")
    bindings[:] = [
        item
        for item in bindings
        if not (
            isinstance(item, Mapping)
            and (
                (
                    item.get("claim_type") == "requirement"
                    and item.get("claim_id") == requirement_id
                )
                or item.get("requirement_id") == requirement_id
            )
            and item.get("source_document_id") == source_document_id
        )
    ]
    bindings.append(
        selection.binding(claim_type="requirement", claim_id=requirement_id)
    )

    decisions = original.setdefault("review_decisions", [])
    if not isinstance(decisions, list):
        raise RequirementMappingError("contract review_decisions must be a list")
    decisions[:] = [
        item
        for item in decisions
        if not (
            isinstance(item, Mapping)
            and item.get("decision_type") == "requirement_upsert"
            and item.get("requirement_id") == requirement_id
            and item.get("source_document_id") == source_document_id
        )
    ]
    decisions.append(
        {
            "decision_type": "requirement_upsert",
            "requirement_id": requirement_id,
            "source_document_id": source_document_id,
            "definition_sha256": definition_sha256,
            "evidence_manifest_sha256": selection.evidence_manifest_sha256,
            "span_ids": list(selection.span_ids),
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
    return RequirementMappingResult(
        contract_path=target,
        requirement_id=requirement_id,
        requirement_status=str(entry["status"]),
        source_document_id=source_document_id,
        span_ids=selection.span_ids,
        definition_sha256=definition_sha256,
        evidence_manifest_sha256=selection.evidence_manifest_sha256,
    )
