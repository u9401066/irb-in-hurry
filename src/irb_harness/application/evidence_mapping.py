"""Bind reviewed workflow claims to verified spans in an evidence manifest."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml

from irb_harness.domain.contracts import OrganizationContract


class EvidenceMappingError(ValueError):
    """Raised when a requested claim-to-span binding cannot be verified."""


@dataclass(frozen=True)
class EvidenceMappingResult:
    contract_path: Path
    transition_event: str
    source_document_id: str
    span_ids: tuple[str, ...]
    evidence_manifest_sha256: str


@dataclass(frozen=True)
class VerifiedEvidenceSelection:
    """Evidence coordinates proven against contract bytes and a manifest."""

    source_document_id: str
    span_ids: tuple[str, ...]
    span_text_sha256: Mapping[str, str]
    evidence_manifest_sha256: str

    def binding(self, *, claim_type: str, claim_id: str) -> dict[str, Any]:
        return {
            "claim_type": claim_type,
            "claim_id": claim_id,
            "source_document_id": self.source_document_id,
            "span_ids": list(self.span_ids),
            "span_text_sha256": dict(self.span_text_sha256),
            "evidence_manifest_sha256": self.evidence_manifest_sha256,
        }


def map_workflow_evidence(
    contract_mapping: Mapping[str, Any],
    *,
    evidence_manifest_path: str | Path,
    transition_event: str,
    source_document_id: str,
    span_ids: Iterable[str],
    output_path: str | Path,
    cache_root: str | Path = ".irb-source-cache",
    update_output: bool = False,
) -> EvidenceMappingResult:
    """Verify selected span IDs and atomically bind them to one workflow transition."""
    original = deepcopy(dict(contract_mapping))
    contract = OrganizationContract.from_mapping(original)
    selection = verify_evidence_selection(
        contract,
        evidence_manifest_path=evidence_manifest_path,
        source_document_id=source_document_id,
        span_ids=span_ids,
    )

    updated = deepcopy(original)
    transition = _find_transition(updated, transition_event)
    references = transition.setdefault("evidence_refs", [])
    if not isinstance(references, list):
        raise EvidenceMappingError("transition evidence_refs must be a list")
    reference = next(
        (
            item
            for item in references
            if isinstance(item, dict)
            and item.get("source_document_id") == source_document_id
        ),
        None,
    )
    if reference is None:
        reference = {"source_document_id": source_document_id}
        references.append(reference)
    reference["locator_status"] = "verified"
    reference["span_ids"] = list(selection.span_ids)

    binding = selection.binding(
        claim_type="workflow_transition", claim_id=transition_event
    )
    bindings = updated.setdefault("evidence_bindings", [])
    if not isinstance(bindings, list):
        raise EvidenceMappingError("evidence_bindings must be a list")
    bindings[:] = [
        item
        for item in bindings
        if not (
            isinstance(item, Mapping)
            and (
                (
                    item.get("claim_type") == "workflow_transition"
                    and item.get("claim_id") == transition_event
                )
                or item.get("transition_event") == transition_event
            )
            and item.get("source_document_id") == source_document_id
        )
    ]
    bindings.append(binding)
    OrganizationContract.from_mapping(updated)

    target = Path(output_path).expanduser().resolve()
    write_contract_mapping(
        updated,
        target,
        cache_root=cache_root,
        organization_id=contract.organization_id,
        update_output=update_output,
    )
    return EvidenceMappingResult(
        contract_path=target,
        transition_event=transition_event,
        source_document_id=source_document_id,
        span_ids=selection.span_ids,
        evidence_manifest_sha256=selection.evidence_manifest_sha256,
    )


def verify_evidence_selection(
    contract: OrganizationContract,
    *,
    evidence_manifest_path: str | Path,
    source_document_id: str,
    span_ids: Iterable[str],
) -> VerifiedEvidenceSelection:
    """Verify source bytes and requested spans without deciding what they mean."""
    selected_spans = tuple(dict.fromkeys(span_ids))
    if not selected_spans:
        raise EvidenceMappingError("at least one evidence span_id is required")
    source = next(
        (
            item
            for item in contract.source_documents
            if item.source_id == source_document_id
        ),
        None,
    )
    if source is None:
        raise EvidenceMappingError(f"unknown source_document_id: {source_document_id}")
    if not source.sha256:
        raise EvidenceMappingError(
            f"source document is not hashed: {source_document_id}"
        )
    manifest_path = Path(evidence_manifest_path).expanduser().resolve()
    manifest_bytes = manifest_path.read_bytes()
    try:
        manifest = json.loads(manifest_bytes)
    except json.JSONDecodeError as exc:
        raise EvidenceMappingError("evidence manifest is not valid JSON") from exc
    if not isinstance(manifest, Mapping):
        raise EvidenceMappingError("evidence manifest root must be a mapping")
    evidence_sha256, spans = _evidence_catalog(manifest, source_document_id)
    if evidence_sha256 != source.sha256:
        raise EvidenceMappingError(
            "evidence bytes do not match the contract source SHA-256"
        )
    unknown_spans = set(selected_spans) - set(spans)
    if unknown_spans:
        raise EvidenceMappingError(
            f"span IDs are absent from the evidence manifest: {sorted(unknown_spans)}"
        )
    return VerifiedEvidenceSelection(
        source_document_id=source_document_id,
        span_ids=selected_spans,
        span_text_sha256={
            span_id: str(spans[span_id]["text_sha256"]) for span_id in selected_spans
        },
        evidence_manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
    )


def _evidence_catalog(
    manifest: Mapping[str, Any], source_document_id: str
) -> tuple[str, dict[str, Mapping[str, Any]]]:
    documents = manifest.get("documents")
    if isinstance(documents, list):
        matches = [
            item
            for item in documents
            if isinstance(item, Mapping) and item.get("source_id") == source_document_id
        ]
        if len(matches) != 1:
            raise EvidenceMappingError(
                "compiled evidence manifest must contain the source exactly once"
            )
        document = matches[0]
        return str(document.get("byte_sha256") or ""), _span_catalog([document])

    assets = manifest.get("assets")
    if isinstance(assets, list):
        matches = [
            item
            for item in assets
            if isinstance(item, Mapping) and item.get("asset_id") == source_document_id
        ]
        if len(matches) != 1:
            raise EvidenceMappingError(
                "source-sync manifest must contain the asset exactly once"
            )
        asset = matches[0]
        evidence_documents = []
        for item in asset.get("documents", []):
            if isinstance(item, Mapping) and isinstance(item.get("evidence"), Mapping):
                evidence_documents.append(item["evidence"])
        return str(asset.get("byte_sha256") or ""), _span_catalog(evidence_documents)
    raise EvidenceMappingError("unrecognized evidence manifest format")


def _span_catalog(
    documents: Iterable[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for document in documents:
        raw_spans = document.get("spans", [])
        if not isinstance(raw_spans, list):
            raise EvidenceMappingError("evidence spans must be a list")
        for span in raw_spans:
            if not isinstance(span, Mapping):
                raise EvidenceMappingError("evidence span must be a mapping")
            span_id = span.get("span_id")
            if not isinstance(span_id, str) or not span_id:
                raise EvidenceMappingError(
                    "evidence span_id must be a non-empty string"
                )
            text_sha256 = span.get("text_sha256")
            if (
                not isinstance(text_sha256, str)
                or len(text_sha256) != 64
                or any(character not in "0123456789abcdef" for character in text_sha256)
            ):
                raise EvidenceMappingError(
                    f"evidence span has an invalid text SHA-256: {span_id}"
                )
            if span_id in result:
                raise EvidenceMappingError(f"duplicate evidence span_id: {span_id}")
            result[span_id] = span
    return result


def _find_transition(contract: dict[str, Any], event: str) -> dict[str, Any]:
    workflow = contract.get("workflow")
    if not isinstance(workflow, Mapping):
        raise EvidenceMappingError("contract workflow must be a mapping")
    transitions = workflow.get("transitions")
    if not isinstance(transitions, list):
        raise EvidenceMappingError("workflow transitions must be a list")
    matches = [
        item
        for item in transitions
        if isinstance(item, dict) and item.get("event") == event
    ]
    if len(matches) != 1:
        raise EvidenceMappingError(f"workflow event must exist exactly once: {event}")
    return matches[0]


def write_contract_mapping(
    contract_mapping: Mapping[str, Any],
    target: str | Path,
    *,
    cache_root: str | Path,
    organization_id: str,
    update_output: bool,
) -> None:
    """Write derived contract bytes atomically and snapshot explicit replacements."""
    resolved_target = Path(target).expanduser().resolve()
    cache = Path(cache_root).expanduser().resolve()
    payload = yaml.safe_dump(
        dict(contract_mapping), allow_unicode=True, sort_keys=False
    ).encode("utf-8")
    if resolved_target.exists() and resolved_target.read_bytes() != payload:
        if not update_output:
            raise FileExistsError(
                f"refusing to overwrite existing contract output: {resolved_target}"
            )
        previous = resolved_target.read_bytes()
        digest = hashlib.sha256(previous).hexdigest()
        snapshot = cache / organization_id / "contract-snapshots" / f"{digest}.yml"
        if not snapshot.exists():
            _atomic_write(snapshot, previous)
    if not resolved_target.exists() or resolved_target.read_bytes() != payload:
        _atomic_write(resolved_target, payload)


def _atomic_write(target: Path, payload: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", dir=target.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
