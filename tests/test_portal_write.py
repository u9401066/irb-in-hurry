"""Regression tests for reviewed contract-to-browser draft writes."""

from __future__ import annotations

import pytest

from irb_harness.application.page_mapping import (
    sanitize_page_discovery,
    write_page_mapping,
)
from irb_harness.application.portal_write import (
    PortalWriteError,
    resolve_legacy_selector_write,
    resolve_reviewed_portal_write,
)
from irb_harness.application.website_binding import bind_requirement_to_control
from irb_harness.infrastructure.contract_loader import (
    load_contract,
    load_contract_mapping,
)


def _bound_contract(tmp_path, *, value_type: str = "string"):
    contract = load_contract_mapping()
    contract["requirements"].append(
        {
            "requirement_id": "kmuh_portal_plan_name",
            "title": "eIRB 計畫名稱欄位",
            "kind": "portal_field",
            "status": "needs_evidence",
            "required": True,
            "value_type": value_type,
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
    discovery = {
        "site_id": "kmuh_eirb",
        "title_sha256": "a" * 64,
        "title_length": 8,
        "url": "https://erec.kmuh.org.tw/RECManageSystem/Case/Edit",
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
                "action_risk": "draft_write",
            }
        ],
        "values_included": False,
    }
    mapping = sanitize_page_discovery(discovery)
    mapping_root = tmp_path / "maps"
    mapping_path = (
        mapping_root / "kmuh" / "kmuh_eirb" / f"{mapping['mapping_sha256']}.json"
    )
    write_page_mapping(discovery, mapping_path)
    output = tmp_path / "contract.yml"
    bind_requirement_to_control(
        contract,
        requirement_id="kmuh_portal_plan_name",
        site_id="kmuh_eirb",
        mapping_sha256=mapping["mapping_sha256"],
        control_id=mapping["controls"][0]["control_id"],
        output_path=output,
        mapping_root=mapping_root,
        cache_root=tmp_path / "cache",
    )
    return load_contract(output), mapping_root, mapping


def test_reviewed_portal_write_resolves_exact_contract_binding(tmp_path):
    contract, mapping_root, mapping = _bound_contract(tmp_path)

    target = resolve_reviewed_portal_write(
        contract,
        requirement_id="kmuh_portal_plan_name",
        site_id="kmuh_eirb",
        mapping_sha256=mapping["mapping_sha256"],
        value="測試計畫",
        mapping_root=mapping_root,
    )

    assert target.binding.selector == "#PlanName"
    assert target.binding.control_id == mapping["controls"][0]["control_id"]
    assert target.value == "測試計畫"


def test_portal_write_rejects_unreviewed_selector_and_mapping(tmp_path):
    contract, mapping_root, mapping = _bound_contract(tmp_path)

    with pytest.raises(PortalWriteError, match="exactly one reviewed"):
        resolve_legacy_selector_write(
            contract,
            site_id="kmuh_eirb",
            selector="#Arbitrary",
            value="unsafe",
            mapping_root=mapping_root,
        )

    with pytest.raises(PortalWriteError, match="does not match"):
        resolve_reviewed_portal_write(
            contract,
            requirement_id="kmuh_portal_plan_name",
            site_id="kmuh_eirb",
            mapping_sha256="f" * 64,
            value="unsafe",
            mapping_root=mapping_root,
        )


def test_portal_write_validates_declared_value_type(tmp_path):
    contract, mapping_root, mapping = _bound_contract(tmp_path, value_type="integer")

    with pytest.raises(PortalWriteError, match="base-10 digits"):
        resolve_reviewed_portal_write(
            contract,
            requirement_id="kmuh_portal_plan_name",
            site_id="kmuh_eirb",
            mapping_sha256=mapping["mapping_sha256"],
            value="not-a-number",
            mapping_root=mapping_root,
        )
