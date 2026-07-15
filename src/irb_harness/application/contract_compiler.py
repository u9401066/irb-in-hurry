"""Compile organization-provided documents into a reviewable contract draft."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

import yaml

from irb_harness.domain.contracts import OrganizationContract
from irb_harness.infrastructure.document_ingest import IngestedDocument, ingest_document


def compile_contract_from_documents(
    institution_id: str,
    institution_name: str,
    document_paths: Iterable[str | Path],
    output_path: str | Path,
    *,
    base_contract: dict[str, Any] | None = None,
    force: bool = False,
) -> tuple[Path, Path]:
    """Create a deterministic contract draft plus citation-ready evidence index."""
    target = Path(output_path)
    evidence_target = target.with_suffix(".evidence.json")
    if not force and (target.exists() or evidence_target.exists()):
        raise FileExistsError(
            f"refusing to overwrite existing contract output: {target}"
        )

    ingested_documents = [
        ingest_document(path, institution_id=institution_id) for path in document_paths
    ]
    documents_by_id: dict[str, IngestedDocument] = {}
    for document in ingested_documents:
        previous = documents_by_id.get(document.source_id)
        if (
            previous is None
            or document.source_name_sha256 < previous.source_name_sha256
        ):
            documents_by_id[document.source_id] = document
    documents = [documents_by_id[source_id] for source_id in sorted(documents_by_id)]
    contract = (
        deepcopy(base_contract)
        if base_contract is not None
        else _empty_contract(institution_id, institution_name)
    )
    contract["schema_version"] = "1.0"
    contract["contract_id"] = str(
        contract.get("contract_id") or f"{institution_id}-irb"
    )
    contract["status"] = "draft"
    contract["organization"] = {
        **dict(contract.get("organization") or {}),
        "id": institution_id,
        "name": institution_name,
        "default_locale": (contract.get("organization") or {}).get(
            "default_locale", "zh-TW"
        ),
    }
    source_documents = list(contract.get("source_documents") or [])
    existing_ids = {
        item.get("source_id") for item in source_documents if isinstance(item, dict)
    }
    for document in documents:
        if document.source_id not in existing_ids:
            source_documents.append(document.contract_source())
    contract["source_documents"] = source_documents
    contract.pop("compiled_at", None)
    contract["compiler"] = {
        "mode": "deterministic_ingest",
        "rule_inference": "not_performed",
        "review_required": True,
        "local_absolute_paths_included": False,
    }

    evidence = {
        "schema_version": "1.0",
        "contract_id": contract["contract_id"],
        "documents": [document.evidence_record() for document in documents],
    }

    OrganizationContract.from_mapping(contract)

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        yaml.safe_dump(contract, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    evidence_target.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target, evidence_target


def _empty_contract(institution_id: str, institution_name: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "contract_id": f"{institution_id}-irb",
        "status": "draft",
        "organization": {
            "id": institution_id,
            "name": institution_name,
            "default_locale": "zh-TW",
        },
        "source_documents": [],
        "workflow": {"states": [], "transitions": []},
        "requirements": [],
        "evidence_bindings": [],
        "website_bindings": [],
        "form_sets": [],
        "websites": [],
    }
