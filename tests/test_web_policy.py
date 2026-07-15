"""Safety policy tests for human-login eIRB browser control."""

from __future__ import annotations

import pytest

from irb_harness.domain.contracts import ActionRisk
from irb_harness.infrastructure.contract_loader import load_contract
from irb_harness.infrastructure.web_policy import (
    BrowserPolicyError,
    assert_allowed_url,
    classify_action,
    page_fingerprint,
    redact_url,
)


def test_redact_url_preserves_route_and_query_keys_only():
    value = redact_url("https://erec.kmuh.org.tw/Case/Edit?id=123&token=secret")

    assert value.startswith("https://erec.kmuh.org.tw/Case/Edit?")
    assert "id=%3Credacted%3E" in value
    assert "token=%3Credacted%3E" in value
    assert "123" not in value
    assert "secret" not in value


def test_allowed_url_is_contract_scoped():
    website = load_contract().website("kmuh_eirb")

    assert_allowed_url("https://erec.kmuh.org.tw/RECManageSystem/Home/Index", website)
    with pytest.raises(BrowserPolicyError, match="not allowed"):
        assert_allowed_url("https://example.com/steal", website)
    with pytest.raises(BrowserPolicyError, match="HTTPS"):
        assert_allowed_url(
            "http://erec.kmuh.org.tw/RECManageSystem/Home/Index", website
        )


@pytest.mark.parametrize(
    ("label", "element_type", "expected"),
    [
        ("查詢案件", "button", ActionRisk.READ),
        ("暫存草稿", "button", ActionRisk.DRAFT_WRITE),
        ("確認送出", "button", ActionRisk.SUBMIT),
        ("刪除案件", "button", ActionRisk.DESTRUCTIVE),
        ("", "submit", ActionRisk.SUBMIT),
    ],
)
def test_action_risk_classification(label, element_type, expected):
    assert classify_action(label, element_type=element_type) is expected


def test_page_fingerprint_does_not_depend_on_query_values():
    first = page_fingerprint(
        "https://erec.kmuh.org.tw/Case/Edit?id=1", "Edit", ["計畫名稱"]
    )
    second = page_fingerprint(
        "https://erec.kmuh.org.tw/Case/Edit?id=2", "Edit", ["計畫名稱"]
    )

    assert first == second
