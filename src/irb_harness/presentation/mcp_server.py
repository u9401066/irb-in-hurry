"""MCP tools for KMUH contract inspection and human-login browser discovery."""

from __future__ import annotations

import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from irb_harness.application.page_mapping import (
    load_page_mapping,
    sanitize_page_discovery,
)
from irb_harness.infrastructure.browser_session import BrowserController
from irb_harness.infrastructure.contract_loader import contract_sha256, load_contract


mcp = FastMCP(
    "irb-harness",
    instructions=(
        "Use organization contracts as authoritative workflow metadata. Browser tools attach only "
        "to a browser session that a human has already authenticated. Never request credentials. "
        "Page discovery omits field values. No submit or destructive browser tool is exposed."
    ),
)

_browser = BrowserController()


@mcp.tool()
def irb_contract_summary(organization_id: str = "kmuh") -> dict[str, Any]:
    """Validate and summarize the selected organization contract; KMUH is the default."""
    contract = load_contract(organization_id=organization_id)
    result = contract.summary()
    result["contract_sha256"] = contract_sha256(contract)
    return result


@mcp.tool()
def irb_requirements(
    organization_id: str = "kmuh",
    submission_type: str | None = None,
    review_track: str | None = None,
    workflow_event: str | None = None,
) -> dict[str, Any]:
    """List applicable institutional requirements and their evidence readiness."""
    contract = load_contract(organization_id=organization_id)
    selected = contract.requirements_for(
        submission_type=submission_type,
        review_track=review_track,
        workflow_event=workflow_event,
    )
    return {
        "contract_id": contract.contract_id,
        "count": len(selected),
        "requirements": [item.summary() for item in selected],
    }


@mcp.tool()
def irb_browser_bridge_status() -> dict[str, Any]:
    """Check whether the human-authenticated Chrome CDP bridge is reachable."""
    return _browser.endpoint_status()


@mcp.tool()
async def irb_browser_list_pages() -> list[dict[str, str | int]]:
    """List open pages with redacted URLs and hashed titles; reads no form values."""
    return await _browser.list_pages()


@mcp.tool()
async def irb_site_session_status(
    site_id: str, organization_id: str = "kmuh", page_ref: str | None = None
) -> dict[str, Any]:
    """Report whether an open institution page appears human-authenticated."""
    contract = load_contract(organization_id=organization_id)
    return await _browser.session_status(contract.website(site_id), page_ref=page_ref)


@mcp.tool()
async def irb_discover_current_page(
    site_id: str, organization_id: str = "kmuh", page_ref: str | None = None
) -> dict[str, Any]:
    """Build a read-only DOM control map; field values and body text are never returned."""
    contract = load_contract(organization_id=organization_id)
    return await _browser.discover_current_page(
        contract.website(site_id), page_ref=page_ref
    )


@mcp.tool()
async def irb_sanitized_page_mapping(
    site_id: str, organization_id: str = "kmuh", page_ref: str | None = None
) -> dict[str, Any]:
    """Return a value-free page map with labels reduced to hashes; writes no files."""
    contract = load_contract(organization_id=organization_id)
    discovery = await _browser.discover_current_page(
        contract.website(site_id), page_ref=page_ref
    )
    return sanitize_page_discovery(discovery)


@mcp.tool()
async def irb_click_reviewed_control(
    site_id: str,
    mapping_sha256: str,
    control_id: str,
    human_confirmed: bool = False,
    organization_id: str = "kmuh",
    page_ref: str | None = None,
) -> dict[str, Any]:
    """Click one human-reviewed read-risk control; never clicks write or submit risk.

    The server must be started with IRB_WEB_CLICK_MODE=reviewed. The mapping
    artifact, live page fingerprint, selector uniqueness, and live risk are all
    rechecked. Set human_confirmed only for the exact reviewed control.
    """
    contract = load_contract(organization_id=organization_id)
    mapping = load_page_mapping(
        organization_id=organization_id,
        site_id=site_id,
        mapping_sha256=mapping_sha256,
        mapping_root=os.environ.get("IRB_WEB_MAPPING_ROOT", ".irb-web-artifacts"),
    )
    return await _browser.click_reviewed_control(
        contract.website(site_id),
        mapping=mapping,
        control_id=control_id,
        human_confirmed=human_confirmed,
        page_ref=page_ref,
    )


@mcp.tool()
async def irb_fill_draft_field(
    site_id: str,
    selector: str,
    value: str,
    human_confirmed: bool = False,
    organization_id: str = "kmuh",
    page_ref: str | None = None,
) -> dict[str, Any]:
    """Fill one draft field after explicit human confirmation; never submits the page.

    The server must also be started with IRB_WEB_WRITE_MODE=draft. Do not set
    human_confirmed unless the user explicitly approved this exact field and value.
    """
    contract = load_contract(organization_id=organization_id)
    return await _browser.fill_draft_field(
        contract.website(site_id),
        selector=selector,
        value=value,
        human_confirmed=human_confirmed,
        page_ref=page_ref,
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
