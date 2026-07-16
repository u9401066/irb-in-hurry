"""Regression tests for evidence-backed institutional requirement mapping."""

from __future__ import annotations

import json

import pytest
import yaml

from irb_harness.application.contract_compiler import compile_contract_from_documents
from irb_harness.application.requirement_mapping import (
    RequirementMappingError,
    map_requirement_from_evidence,
)
from irb_harness.infrastructure.contract_loader import load_contract


def test_reviewed_span_becomes_queryable_verified_requirement(tmp_path):
    source = tmp_path / "organization-guide.md"
    source.write_text(
        "新案必須檢附研究計畫書。\n送出前由主持人確認。\n",
        encoding="utf-8",
    )
    draft_path = tmp_path / "draft.yml"
    contract_path, evidence_path = compile_contract_from_documents(
        "example",
        "Example IRB",
        [source],
        draft_path,
    )
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    source_id = contract["source_documents"][0]["source_id"]
    span_id = evidence["documents"][0]["spans"][0]["span_id"]
    definition = {
        "requirement_id": "example_new_protocol",
        "title": "新案研究計畫書",
        "kind": "document",
        "required": True,
        "value_type": "file",
        "data_path": "attachments.protocol",
        "applies_to": {
            "submission_types": ["new"],
            "review_tracks": ["expedited"],
        },
    }
    output = tmp_path / "reviewed.yml"

    result = map_requirement_from_evidence(
        contract,
        requirement_definition=definition,
        evidence_manifest_path=evidence_path,
        source_document_id=source_id,
        span_ids=[span_id],
        output_path=output,
        locator_hint="第一行",
        cache_root=tmp_path / "cache",
    )

    reviewed = load_contract(output)
    selected = reviewed.requirements_for(
        submission_type="new", review_track="expedited"
    )
    assert result.requirement_status == "verified"
    assert [item.requirement_id for item in selected] == ["example_new_protocol"]
    assert selected[0].evidence_refs[0].span_ids == (span_id,)
    assert reviewed.evidence_bindings[0].claim_type == "requirement"
    assert reviewed.evidence_bindings[0].claim_id == "example_new_protocol"
    raw = yaml.safe_load(output.read_text(encoding="utf-8"))
    assert raw["review_decisions"][0]["automated_rule_inference"] is False
    assert len(raw["review_decisions"][0]["definition_sha256"]) == 64

    with pytest.raises(RequirementMappingError, match="already exists"):
        map_requirement_from_evidence(
            raw,
            requirement_definition=definition,
            evidence_manifest_path=evidence_path,
            source_document_id=source_id,
            span_ids=[span_id],
            output_path=tmp_path / "duplicate.yml",
            cache_root=tmp_path / "cache",
        )


def test_kmuh_default_requirements_are_explicit_and_need_evidence():
    contract = load_contract()
    selected = contract.requirements_for(
        submission_type="new",
        review_track="general",
        workflow_event="submit_new",
    )

    assert {item.requirement_id for item in selected} == {
        "kmuh_new_online_application",
        "kmuh_new_submission_checklist",
    }
    assert all(item.evidence_refs for item in contract.requirements)
    assert set(contract.summary()["requirements_needing_evidence"]) == {
        item.requirement_id for item in contract.requirements
    }
