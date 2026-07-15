"""MCP surface regression tests."""

from __future__ import annotations

import asyncio

import pytest

from irb_harness.infrastructure.browser_session import BrowserController
from irb_harness.infrastructure.contract_loader import load_contract
from irb_harness.infrastructure.web_policy import BrowserPolicyError
from irb_harness.presentation.mcp_server import mcp


def test_mcp_surface_has_discovery_and_no_submit_or_delete_tools():
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}

    assert "irb_contract_summary" in names
    assert "irb_requirements" in names
    assert "irb_discover_current_page" in names
    assert "irb_sanitized_page_mapping" in names
    assert "irb_click_reviewed_control" in names
    assert "irb_fill_draft_field" in names
    assert "irb_fill_reviewed_requirement" in names
    assert not any("submit" in name or "delete" in name for name in names)


def test_draft_write_is_disabled_before_browser_attachment(monkeypatch):
    monkeypatch.delenv("IRB_WEB_WRITE_MODE", raising=False)
    website = load_contract().website("kmuh_eirb")
    controller = BrowserController("http://127.0.0.1:9")

    with pytest.raises(BrowserPolicyError, match="disabled"):
        asyncio.run(
            controller.fill_draft_field(
                website,
                selector="#title",
                value="test",
                human_confirmed=True,
            )
        )


def test_reviewed_click_is_disabled_before_browser_attachment(monkeypatch):
    monkeypatch.delenv("IRB_WEB_CLICK_MODE", raising=False)
    website = load_contract().website("kmuh_eirb")
    controller = BrowserController("http://127.0.0.1:9")

    with pytest.raises(BrowserPolicyError, match="disabled"):
        asyncio.run(
            controller.click_reviewed_control(
                website,
                mapping={},
                control_id="control",
                human_confirmed=True,
            )
        )
