"""Regression tests for reviewed portal requirement-to-control bindings."""

from __future__ import annotations

from irb_harness.application.page_mapping import (
    sanitize_page_discovery,
    write_page_mapping,
)
from irb_harness.application.website_binding import (
    WebsiteBindingError,
    bind_requirement_to_control,
)
from irb_harness.infrastructure.contract_loader import (
    load_contract,
    load_contract_mapping,
)


def _discovery(action_risk: str = "read"):
    return {
        "site_id": "kmuh_eirb",
        "title_sha256": "a" * 64,
        "title_length": 8,
        "url": "https://erec.kmuh.org.tw/RECManageSystem/Case/Edit?id=%3Credacted%3E",
        "page_fingerprint": "b" * 64,
        "control_count": 1,
        "controls": [
            {
                "tag": "input",
                "type": "text",
                "label": "計畫名稱",
                "selector": "#PlanName",
                "required": True,
                "disabled": False,
                "readonly": False,
                "option_count": None,
                "action_risk": action_risk,
            }
        ],
        "values_included": False,
    }


def _contract_with_portal_requirement():
    contract = load_contract_mapping()
    contract["requirements"].append(
        {
            "requirement_id": "kmuh_portal_plan_name",
            "title": "eIRB 計畫名稱欄位",
            "kind": "portal_field",
            "status": "needs_evidence",
            "required": True,
            "value_type": "string",
            "data_path": "study.title_zh",
            "applies_to": {
                "submission_types": ["new"],
                "workflow_events": ["submit_new"],
            },
            "evidence_refs": [
                {
                    "source_document_id": "kmuh_sop_02_03",
                    "locator_status": "needs_retrieval",
                }
            ],
        }
    )
    return contract


def test_portal_requirement_binds_only_to_hashed_reviewed_field(tmp_path):
    discovery = _discovery()
    mapping = sanitize_page_discovery(discovery)
    mapping_path = (
        tmp_path / "maps" / "kmuh" / "kmuh_eirb" / f"{mapping['mapping_sha256']}.json"
    )
    write_page_mapping(discovery, mapping_path)
    control_id = mapping["controls"][0]["control_id"]
    output = tmp_path / "contract.yml"

    bind_requirement_to_control(
        _contract_with_portal_requirement(),
        requirement_id="kmuh_portal_plan_name",
        site_id="kmuh_eirb",
        mapping_sha256=mapping["mapping_sha256"],
        control_id=control_id,
        output_path=output,
        mapping_root=tmp_path / "maps",
        cache_root=tmp_path / "cache",
    )

    contract = load_contract(output)
    requirement = next(
        item
        for item in contract.requirements
        if item.requirement_id == "kmuh_portal_plan_name"
    )
    assert requirement.website_site_id == "kmuh_eirb"
    assert requirement.page_mapping_sha256 == mapping["mapping_sha256"]
    assert requirement.control_id == control_id
    assert contract.website_bindings[0].selector == "#PlanName"


def test_portal_requirement_rejects_destructive_mapped_control(tmp_path):
    discovery = _discovery(action_risk="destructive")
    mapping = sanitize_page_discovery(discovery)
    mapping_path = (
        tmp_path / "maps" / "kmuh" / "kmuh_eirb" / f"{mapping['mapping_sha256']}.json"
    )
    write_page_mapping(discovery, mapping_path)

    try:
        bind_requirement_to_control(
            _contract_with_portal_requirement(),
            requirement_id="kmuh_portal_plan_name",
            site_id="kmuh_eirb",
            mapping_sha256=mapping["mapping_sha256"],
            control_id=mapping["controls"][0]["control_id"],
            output_path=tmp_path / "invalid.yml",
            mapping_root=tmp_path / "maps",
            cache_root=tmp_path / "cache",
        )
    except WebsiteBindingError as exc:
        assert "submit or destructive" in str(exc)
    else:
        raise AssertionError("destructive control binding must be rejected")
