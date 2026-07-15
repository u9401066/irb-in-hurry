"""Regression tests for value-free browser mapping artifacts."""

from __future__ import annotations

import json

import pytest

from irb_harness.application.page_mapping import (
    PageMappingError,
    load_page_mapping,
    sanitize_page_discovery,
    write_page_mapping,
)


def _discovery():
    digest = "a" * 64
    return {
        "site_id": "kmuh_eirb",
        "title_sha256": digest,
        "title_length": 12,
        "url": "https://erec.kmuh.org.tw/RECManageSystem/Case/Edit?id=%3Credacted%3E",
        "page_fingerprint": "b" * 64,
        "control_count": 2,
        "controls": [
            {
                "tag": "input",
                "type": "text",
                "id": "PlanName",
                "name": "PlanName",
                "label": "計畫名稱",
                "selector": "#PlanName",
                "required": True,
                "disabled": False,
                "readonly": False,
                "option_count": None,
                "action_risk": "read",
            },
            {
                "tag": "button",
                "type": "submit",
                "id": "Submit",
                "name": None,
                "label": "確認送出",
                "selector": "#Submit",
                "required": False,
                "disabled": False,
                "readonly": False,
                "option_count": None,
                "action_risk": "submit",
            },
        ],
        "values_included": False,
    }


def test_sanitized_mapping_keeps_selectors_but_not_raw_labels():
    mapping = sanitize_page_discovery(_discovery())
    serialized = json.dumps(mapping, ensure_ascii=False)

    assert mapping["control_count"] == 2
    assert mapping["controls"][0]["selector"] == "#PlanName"
    assert len(mapping["controls"][0]["label_sha256"]) == 64
    assert "計畫名稱" not in serialized
    assert "確認送出" not in serialized
    assert mapping["privacy"]["field_values_included"] is False


def test_mapping_rejects_payload_that_contains_a_field_value():
    discovery = _discovery()
    discovery["controls"][0]["value"] = "敏感研究名稱"

    with pytest.raises(PageMappingError, match="forbidden sensitive field"):
        sanitize_page_discovery(discovery)


def test_mapping_write_refuses_implicit_overwrite(tmp_path):
    target = tmp_path / "mapping.json"
    first_path, first = write_page_mapping(_discovery(), target)
    assert first_path == target
    assert first["mapping_sha256"]

    changed = _discovery()
    changed["controls"][0]["required"] = False
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        write_page_mapping(changed, target)

    write_page_mapping(changed, target, force=True)
    assert (
        json.loads(target.read_text(encoding="utf-8"))["controls"][0]["required"]
        is False
    )


def test_content_addressed_mapping_loader_rejects_tampering(tmp_path):
    mapping = sanitize_page_discovery(_discovery())
    target = tmp_path / "kmuh" / "kmuh_eirb" / f"{mapping['mapping_sha256']}.json"
    write_page_mapping(_discovery(), target)

    loaded = load_page_mapping(
        organization_id="kmuh",
        site_id="kmuh_eirb",
        mapping_sha256=mapping["mapping_sha256"],
        mapping_root=tmp_path,
    )
    assert loaded["mapping_sha256"] == mapping["mapping_sha256"]

    loaded["controls"][0]["action_risk"] = "submit"
    target.write_text(json.dumps(loaded), encoding="utf-8")
    with pytest.raises(PageMappingError, match="verification failed"):
        load_page_mapping(
            organization_id="kmuh",
            site_id="kmuh_eirb",
            mapping_sha256=mapping["mapping_sha256"],
            mapping_root=tmp_path,
        )
