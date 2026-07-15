"""Regression tests for human-defined, evidence-backed workflow transitions."""

from __future__ import annotations

import json

import pytest
import yaml

from irb_harness.application.contract_compiler import compile_contract_from_documents
from irb_harness.application.workflow_mapping import (
    WorkflowMappingError,
    map_workflow_from_evidence,
)
from irb_harness.infrastructure.contract_loader import load_contract


def test_empty_compiled_contract_can_add_first_reviewed_workflow(tmp_path):
    source = tmp_path / "official-guidance.md"
    source.write_text("研究者完成草稿後，經人工確認始得送出。\n", encoding="utf-8")
    compiled_path, evidence_path = compile_contract_from_documents(
        "example",
        "Example IRB",
        [source],
        tmp_path / "compiled.yml",
    )
    compiled = yaml.safe_load(compiled_path.read_text(encoding="utf-8"))
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    source_id = evidence["documents"][0]["source_id"]
    span_id = evidence["documents"][0]["spans"][0]["span_id"]
    definition = {
        "event": "submit_new",
        "from": "draft",
        "to": "submitted",
        "action_risk": "submit",
        "human_confirmation": True,
        "evidence_refs": [
            {
                "source_document_id": "untrusted-caller-value",
                "locator_status": "verified",
                "span_ids": ["fake"],
            }
        ],
    }
    output = tmp_path / "mapped.yml"

    result = map_workflow_from_evidence(
        compiled,
        transition_definition=definition,
        evidence_manifest_path=evidence_path,
        source_document_id=source_id,
        span_ids=[span_id],
        output_path=output,
        cache_root=tmp_path / "cache",
    )

    contract = load_contract(output)
    transition = contract.workflow_transitions[0]
    assert transition.event == "submit_new"
    assert transition.from_states == ("draft",)
    assert transition.to_state == "submitted"
    assert transition.evidence_refs[0].source_document_id == source_id
    assert transition.evidence_refs[0].span_ids == (span_id,)
    assert contract.workflow_states == ("draft", "submitted")
    assert result.states_added == ("draft", "submitted")
    assert contract.evidence_bindings[0].claim_type == "workflow_transition"
    written = yaml.safe_load(output.read_text(encoding="utf-8"))
    decision = written["review_decisions"][0]
    assert decision["automated_rule_inference"] is False
    assert decision["definition_sha256"] == result.definition_sha256
    assert decision["states_added"] == ["draft", "submitted"]

    with pytest.raises(WorkflowMappingError, match="already exists"):
        map_workflow_from_evidence(
            written,
            transition_definition=definition,
            evidence_manifest_path=evidence_path,
            source_document_id=source_id,
            span_ids=[span_id],
            output_path=tmp_path / "duplicate.yml",
            cache_root=tmp_path / "cache",
        )
