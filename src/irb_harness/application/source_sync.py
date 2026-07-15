"""Synchronize contract-declared sources into an evidence-bearing workspace override."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import yaml

from irb_harness.domain.contracts import OrganizationContract
from irb_harness.infrastructure.contract_loader import contract_sha256
from irb_harness.infrastructure.document_ingest import ingest_document
from irb_harness.infrastructure.source_archive import (
    RetrievedAsset,
    expand_zip_asset,
    retrieve_asset,
)


class SourceSyncError(RuntimeError):
    """Raised when source synchronization cannot produce a safe override."""


@dataclass(frozen=True)
class AssetRequest:
    collection: str
    id_key: str
    asset_id: str
    url: str
    expected_media_type: str | None


@dataclass(frozen=True)
class SourceSyncResult:
    contract_path: Path
    manifest_path: Path
    retrieved_ids: tuple[str, ...]
    failed_ids: tuple[str, ...]


Retriever = Callable[..., RetrievedAsset]


def sync_contract_sources(
    contract_mapping: Mapping[str, Any],
    *,
    output_path: str | Path,
    cache_root: str | Path = ".irb-source-cache",
    source_ids: Iterable[str] = (),
    form_set_ids: Iterable[str] = (),
    continue_on_error: bool = False,
    update_output: bool = False,
    retriever: Retriever = retrieve_asset,
) -> SourceSyncResult:
    """Retrieve selected declared assets, preserve evidence, and write an override."""
    original = deepcopy(dict(contract_mapping))
    contract = OrganizationContract.from_mapping(original)
    cache = Path(cache_root).expanduser().resolve()
    selected_sources = tuple(dict.fromkeys(source_ids))
    selected_forms = tuple(dict.fromkeys(form_set_ids))
    requests = _asset_requests(original, selected_sources, selected_forms)
    if not requests:
        raise SourceSyncError("no contract assets were selected for synchronization")

    successful: dict[str, tuple[AssetRequest, RetrievedAsset, dict[str, Any]]] = {}
    errors: list[dict[str, str]] = []
    for request in requests:
        try:
            asset = retriever(
                organization_id=contract.organization_id,
                asset_id=request.asset_id,
                url=request.url,
                cache_root=cache,
                expected_media_type=request.expected_media_type,
            )
            if _is_zip(request.url, asset):
                asset = expand_zip_asset(asset, cache_root=cache)
            evidence = _asset_evidence(contract.organization_id, request, asset, cache)
            successful[request.asset_id] = (request, asset, evidence)
        except Exception as exc:
            errors.append(
                {
                    "asset_id": request.asset_id,
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
            )

    manifest = {
        "schema_version": "1.0",
        "organization_id": contract.organization_id,
        "contract_id": contract.contract_id,
        "input_contract_sha256": contract_sha256(original),
        "assets": [
            successful[request.asset_id][2]
            for request in requests
            if request.asset_id in successful
        ],
        "errors": errors,
    }
    manifest_path, manifest_sha256 = _write_immutable_manifest(
        manifest, cache, contract.organization_id
    )
    if errors and not continue_on_error:
        failed = ", ".join(item["asset_id"] for item in errors)
        raise SourceSyncError(
            f"source synchronization failed for {failed}; evidence manifest: {manifest_path}"
        )

    updated = deepcopy(original)
    for request, asset, _ in successful.values():
        entry = _find_entry(updated, request)
        entry["sha256"] = asset.sha256
        entry["evidence_status"] = "retrieved_needs_rule_mapping"
        entry["retrieval"] = {
            "media_type": asset.media_type,
            "byte_size": asset.byte_size,
            "cache_path": str(asset.path.relative_to(cache)),
            "final_uri": _redact_url(asset.final_url),
            "member_count": len(asset.members),
        }
        if request.collection == "source_documents":
            _advance_reference_status(updated, request.asset_id)
    updated["source_sync"] = {
        "manifest_path": str(manifest_path.relative_to(cache)),
        "manifest_sha256": manifest_sha256,
        "retrieved_asset_count": len(successful),
        "failed_asset_count": len(errors),
    }
    OrganizationContract.from_mapping(updated)
    target = _write_contract_override(
        updated,
        Path(output_path).expanduser().resolve(),
        cache,
        contract.organization_id,
        update_output=update_output,
    )
    return SourceSyncResult(
        contract_path=target,
        manifest_path=manifest_path,
        retrieved_ids=tuple(successful),
        failed_ids=tuple(item["asset_id"] for item in errors),
    )


def _asset_requests(
    contract: Mapping[str, Any],
    source_ids: tuple[str, ...],
    form_set_ids: tuple[str, ...],
) -> list[AssetRequest]:
    all_sources = {
        str(item["source_id"]): item
        for item in contract.get("source_documents", [])
        if isinstance(item, Mapping)
    }
    all_forms = {
        str(item["form_set_id"]): item
        for item in contract.get("form_sets", [])
        if isinstance(item, Mapping)
    }
    if not source_ids and not form_set_ids:
        source_ids = tuple(all_sources)
        form_set_ids = tuple(all_forms)
    unknown_sources = set(source_ids) - set(all_sources)
    unknown_forms = set(form_set_ids) - set(all_forms)
    if unknown_sources or unknown_forms:
        details = []
        if unknown_sources:
            details.append(f"unknown source IDs: {sorted(unknown_sources)}")
        if unknown_forms:
            details.append(f"unknown form-set IDs: {sorted(unknown_forms)}")
        raise SourceSyncError("; ".join(details))

    requests = [
        AssetRequest(
            collection="source_documents",
            id_key="source_id",
            asset_id=source_id,
            url=str(all_sources[source_id]["uri"]),
            expected_media_type=str(all_sources[source_id].get("media_type") or "")
            or None,
        )
        for source_id in source_ids
    ]
    requests.extend(
        AssetRequest(
            collection="form_sets",
            id_key="form_set_id",
            asset_id=form_set_id,
            url=str(all_forms[form_set_id]["source_uri"]),
            expected_media_type="application/zip",
        )
        for form_set_id in form_set_ids
    )
    return requests


def _asset_evidence(
    organization_id: str,
    request: AssetRequest,
    asset: RetrievedAsset,
    cache: Path,
) -> dict[str, Any]:
    documents: list[dict[str, Any]] = []
    candidates = list(asset.members) if asset.members else [asset]
    for candidate in candidates:
        path = candidate.path
        record: dict[str, Any] = {
            "relative_path": (
                candidate.relative_path
                if hasattr(candidate, "relative_path")
                else path.name
            ),
            "cache_path": str(path.relative_to(cache)),
            "byte_sha256": candidate.sha256,
            "byte_size": candidate.byte_size,
        }
        try:
            ingested = ingest_document(path, institution_id=organization_id)
        except ValueError as exc:
            record["ingest_status"] = "unsupported_needs_adapter"
            record["ingest_error"] = str(exc)
        except Exception as exc:
            record["ingest_status"] = "extraction_failed_needs_review"
            record["ingest_error"] = f"{type(exc).__name__}: {exc}"
        else:
            record["ingest_status"] = "ingested_needs_rule_mapping"
            record["evidence"] = ingested.evidence_record()
        documents.append(record)
    return {
        "asset_id": request.asset_id,
        "contract_collection": request.collection,
        "requested_uri": _redact_url(asset.requested_url),
        "requested_uri_sha256": hashlib.sha256(
            asset.requested_url.encode("utf-8")
        ).hexdigest(),
        "final_uri": _redact_url(asset.final_url),
        "media_type": asset.media_type,
        "byte_sha256": asset.sha256,
        "byte_size": asset.byte_size,
        "cache_path": str(asset.path.relative_to(cache)),
        "cache_reused": asset.reused,
        "documents": documents,
    }


def _find_entry(contract: dict[str, Any], request: AssetRequest) -> dict[str, Any]:
    for entry in contract.get(request.collection, []):
        if isinstance(entry, dict) and entry.get(request.id_key) == request.asset_id:
            return entry
    raise SourceSyncError(f"contract asset disappeared during sync: {request.asset_id}")


def _advance_reference_status(contract: dict[str, Any], source_id: str) -> None:
    """Move retrieved source locators to mapping review without claiming verification."""
    workflow = contract.get("workflow", {})
    transitions = workflow.get("transitions", []) if isinstance(workflow, dict) else []
    requirements = contract.get("requirements", [])
    claims = [
        *(transitions if isinstance(transitions, list) else []),
        *(requirements if isinstance(requirements, list) else []),
    ]
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        references = claim.get("evidence_refs", [])
        if not isinstance(references, list):
            continue
        for reference in references:
            if (
                isinstance(reference, dict)
                and reference.get("source_document_id") == source_id
                and reference.get("locator_status") == "needs_retrieval"
            ):
                reference["locator_status"] = "needs_mapping"


def _is_zip(url: str, asset: RetrievedAsset) -> bool:
    return urlparse(url).path.lower().endswith(".zip") or asset.media_type in {
        "application/zip",
        "application/x-zip-compressed",
    }


def _redact_url(value: str) -> str:
    parsed = urlparse(value)
    query = urlencode(
        [
            (key, "<redacted>")
            for key, _ in parse_qsl(parsed.query, keep_blank_values=True)
        ]
    )
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", query, ""))


def _write_immutable_manifest(
    manifest: Mapping[str, Any], cache: Path, organization_id: str
) -> tuple[Path, str]:
    payload = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    target = cache / organization_id / "manifests" / f"{digest}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise SourceSyncError(f"immutable manifest hash mismatch: {target}")
    else:
        _atomic_write(target, payload)
    return target, digest


def _write_contract_override(
    contract: Mapping[str, Any],
    target: Path,
    cache: Path,
    organization_id: str,
    *,
    update_output: bool,
) -> Path:
    payload = yaml.safe_dump(
        dict(contract), allow_unicode=True, sort_keys=False
    ).encode("utf-8")
    if target.exists() and target.read_bytes() != payload:
        if not update_output:
            raise FileExistsError(
                f"refusing to overwrite existing contract output: {target}"
            )
        previous = target.read_bytes()
        previous_sha = hashlib.sha256(previous).hexdigest()
        snapshot = (
            cache / organization_id / "contract-snapshots" / f"{previous_sha}.yml"
        )
        if not snapshot.exists():
            _atomic_write(snapshot, previous)
    if not target.exists() or target.read_bytes() != payload:
        target.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(target, payload)
    return target


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
