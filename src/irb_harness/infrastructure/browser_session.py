"""Attach to a human-authenticated Chromium session without handling credentials."""

from __future__ import annotations

import hashlib
import os
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import urlopen

from irb_harness.domain.contracts import ActionRisk, WebSiteContract
from irb_harness.infrastructure.web_policy import (
    BrowserPolicyError,
    assert_allowed_url,
    classify_action,
    page_fingerprint,
    redact_url,
)


class BrowserUnavailable(RuntimeError):
    """Raised when the human-authenticated browser bridge is unavailable."""


class HumanLoginRequired(RuntimeError):
    """Raised when an attached page is present but not authenticated."""


class BrowserController:
    """Long-lived CDP attachment used by the MCP server process."""

    def __init__(self, endpoint: str | None = None) -> None:
        self.endpoint = endpoint or os.environ.get(
            "IRB_WEB_CDP_ENDPOINT", "http://127.0.0.1:9222"
        )
        self._playwright: Any = None
        self._browser: Any = None

    def endpoint_status(self) -> dict[str, Any]:
        """Probe CDP metadata without returning the browser websocket URL."""
        version_url = f"{self.endpoint.rstrip('/')}/json/version"
        try:
            with urlopen(version_url, timeout=2) as response:  # noqa: S310 - loopback/configured CDP endpoint
                available = response.status == 200
                reason = None if available else f"http_status_{response.status}"
        except HTTPError as exc:
            available = False
            reason = f"http_status_{exc.code}"
        except URLError as exc:
            available = False
            reason = _connection_reason(exc.reason)
        except (OSError, ValueError) as exc:
            available = False
            reason = _connection_reason(exc)
        result = {
            "endpoint": self.endpoint,
            "available": available,
            "attachment_mode": "existing_human_authenticated_chromium",
            "credentials_handled": False,
        }
        if reason:
            result["reason"] = reason
        return result

    async def connect(self) -> Any:
        if self._browser is not None and self._browser.is_connected():
            return self._browser
        try:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.connect_over_cdp(
                self.endpoint,
                timeout=5000,
            )
        except Exception as exc:
            self._browser = None
            raise BrowserUnavailable(
                f"cannot attach to human-authenticated Chrome at {self.endpoint}"
            ) from exc
        return self._browser

    async def list_pages(self) -> list[dict[str, str | int]]:
        browser = await self.connect()
        pages: list[dict[str, str | int]] = []
        for context_index, context in enumerate(browser.contexts):
            for page_index, page in enumerate(context.pages):
                try:
                    title = await page.title()
                except Exception:
                    title = ""
                pages.append(
                    {
                        "page_ref": f"c{context_index}p{page_index}",
                        "title_sha256": hashlib.sha256(
                            title.encode("utf-8")
                        ).hexdigest(),
                        "title_length": len(title),
                        "url": redact_url(page.url),
                    }
                )
        return pages

    async def session_status(
        self, website: WebSiteContract, *, page_ref: str | None = None
    ) -> dict[str, Any]:
        page, resolved_ref = await self._find_page(website, page_ref=page_ref)
        if page is None:
            return {
                "site_id": website.site_id,
                "status": "page_not_open",
                "instruction": f"Open {website.start_url} in the human-authenticated browser.",
            }
        if await _any_selector_visible(page, website.unauthenticated_selectors):
            return {
                "site_id": website.site_id,
                "status": "human_login_required",
                "page_ref": resolved_ref,
                "url": redact_url(page.url),
            }
        if website.authenticated_selectors and await _any_selector_visible(
            page,
            website.authenticated_selectors,
        ):
            status = "authenticated"
        else:
            status = "unknown"
        return {
            "site_id": website.site_id,
            "status": status,
            "page_ref": resolved_ref,
            "url": redact_url(page.url),
        }

    async def discover_current_page(
        self, website: WebSiteContract, *, page_ref: str | None = None
    ) -> dict[str, Any]:
        """Inventory DOM controls without reading field values or page body text."""
        page, resolved_ref = await self._require_authenticated_page(
            website, page_ref=page_ref
        )
        assert_allowed_url(page.url, website)
        title = await page.title()
        controls = await page.evaluate(_DISCOVERY_SCRIPT)
        for control in controls:
            control["action_risk"] = classify_action(
                control.get("label", ""),
                element_type=control.get("type", ""),
            ).value
        labels = [control.get("label", "") for control in controls]
        return {
            "site_id": website.site_id,
            "page_ref": resolved_ref,
            "title_sha256": hashlib.sha256(title.encode("utf-8")).hexdigest(),
            "title_length": len(title),
            "url": redact_url(page.url),
            "page_fingerprint": page_fingerprint(page.url, title, labels),
            "control_count": len(controls),
            "controls": controls,
            "values_included": False,
        }

    async def fill_draft_field(
        self,
        website: WebSiteContract,
        *,
        selector: str,
        value: str,
        human_confirmed: bool,
        page_ref: str | None = None,
    ) -> dict[str, Any]:
        """Fill one non-secret draft field; never clicks submit or destructive actions."""
        if os.environ.get("IRB_WEB_WRITE_MODE") != "draft":
            raise BrowserPolicyError(
                "draft writes are disabled; set IRB_WEB_WRITE_MODE=draft explicitly"
            )
        if website.draft_writes != "explicit_confirmation":
            raise BrowserPolicyError(
                f"draft writes are disabled by contract for site '{website.site_id}'"
            )
        if not human_confirmed:
            raise BrowserPolicyError(
                "a human must explicitly confirm this draft field write"
            )
        page, resolved_ref = await self._require_authenticated_page(
            website, page_ref=page_ref
        )
        assert_allowed_url(page.url, website)
        locator = page.locator(selector)
        count = await locator.count()
        if count != 1:
            raise BrowserPolicyError(
                f"selector must match exactly one element; matched {count}"
            )
        metadata = await locator.evaluate(_FIELD_METADATA_SCRIPT)
        element_type = str(metadata.get("type", "")).lower()
        if element_type in {"password", "hidden", "file", "submit", "button"}:
            raise BrowserPolicyError(
                f"field type is not draft-fillable: {element_type}"
            )
        risk = classify_action(
            str(metadata.get("label", "")), element_type=element_type
        )
        if risk in {ActionRisk.SUBMIT, ActionRisk.DESTRUCTIVE}:
            raise BrowserPolicyError(
                f"field is classified as {risk.value} and cannot be filled"
            )
        await locator.fill(value)
        return {
            "site_id": website.site_id,
            "page_ref": resolved_ref,
            "selector": selector,
            "status": "draft_field_filled",
            "value_sha256": hashlib.sha256(value.encode("utf-8")).hexdigest(),
            "submitted": False,
        }

    async def click_reviewed_control(
        self,
        website: WebSiteContract,
        *,
        mapping: Mapping[str, Any],
        control_id: str,
        human_confirmed: bool,
        page_ref: str | None = None,
    ) -> dict[str, Any]:
        """Click one reviewed read-only control; never permits write/submit risk."""
        if os.environ.get("IRB_WEB_CLICK_MODE") != "reviewed":
            raise BrowserPolicyError(
                "reviewed clicks are disabled; set IRB_WEB_CLICK_MODE=reviewed explicitly"
            )
        if website.read_actions != "explicit_confirmation":
            raise BrowserPolicyError(
                f"read actions are disabled by contract for site '{website.site_id}'"
            )
        if not human_confirmed:
            raise BrowserPolicyError(
                "a human must explicitly confirm this reviewed control click"
            )
        if mapping.get("site_id") != website.site_id:
            raise BrowserPolicyError(
                "page mapping does not belong to the selected site"
            )
        controls = mapping.get("controls")
        if not isinstance(controls, list):
            raise BrowserPolicyError("page mapping controls are invalid")
        matches = [
            control
            for control in controls
            if isinstance(control, Mapping) and control.get("control_id") == control_id
        ]
        if len(matches) != 1:
            raise BrowserPolicyError(
                "control_id must exist exactly once in the reviewed mapping"
            )
        control = matches[0]
        if control.get("action_risk") != ActionRisk.READ.value:
            raise BrowserPolicyError(
                "only controls reviewed as read risk may be clicked"
            )
        if control.get("disabled") is True:
            raise BrowserPolicyError("disabled reviewed controls cannot be clicked")
        selector = str(control.get("selector") or "")
        if not selector:
            raise BrowserPolicyError("reviewed control is missing a selector")

        page, resolved_ref = await self._require_authenticated_page(
            website, page_ref=page_ref
        )
        discovery = await self.discover_current_page(website, page_ref=resolved_ref)
        if discovery["page_fingerprint"] != mapping.get("page_fingerprint"):
            raise BrowserPolicyError(
                "live page fingerprint differs from the reviewed mapping"
            )
        locator = page.locator(selector)
        count = await locator.count()
        if count != 1:
            raise BrowserPolicyError(
                f"reviewed selector must match exactly one element; matched {count}"
            )
        metadata = await locator.evaluate(_FIELD_METADATA_SCRIPT)
        element_type = str(metadata.get("type", "")).lower()
        if element_type == "submit":
            raise BrowserPolicyError("submit controls cannot be clicked")
        live_risk = classify_action(
            str(metadata.get("label", "")), element_type=element_type
        )
        if live_risk is not ActionRisk.READ:
            raise BrowserPolicyError(
                f"live control is classified as {live_risk.value} and cannot be clicked"
            )
        before_url = redact_url(page.url)
        await locator.click()
        assert_allowed_url(page.url, website)
        return {
            "site_id": website.site_id,
            "page_ref": resolved_ref,
            "control_id": control_id,
            "status": "reviewed_read_control_clicked",
            "before_url": before_url,
            "after_url": redact_url(page.url),
            "submitted": False,
        }

    async def _require_authenticated_page(
        self, website: WebSiteContract, *, page_ref: str | None = None
    ) -> tuple[Any, str]:
        page, resolved_ref = await self._find_page(website, page_ref=page_ref)
        if page is None:
            raise BrowserUnavailable(f"no open page for site '{website.site_id}'")
        if await _any_selector_visible(page, website.unauthenticated_selectors):
            raise HumanLoginRequired(
                f"human login required in the attached Chrome page for site '{website.site_id}'"
            )
        if resolved_ref is None:
            raise BrowserUnavailable("attached page is missing a page reference")
        return page, resolved_ref

    async def _find_page(
        self, website: WebSiteContract, *, page_ref: str | None = None
    ) -> tuple[Any | None, str | None]:
        browser = await self.connect()
        allowed = {host.lower() for host in website.allowed_hosts}
        for context_index, context in enumerate(browser.contexts):
            for page_index, page in enumerate(context.pages):
                current_ref = f"c{context_index}p{page_index}"
                if page_ref is not None and current_ref != page_ref:
                    continue
                try:
                    assert_allowed_url(page.url, website)
                except BrowserPolicyError:
                    continue
                host = (urlparse(page.url).hostname or "").lower()
                if host in allowed:
                    return page, current_ref
        return None, page_ref


async def _any_selector_visible(page: Any, selectors: tuple[str, ...]) -> bool:
    for selector in selectors:
        try:
            locator = page.locator(selector)
            for index in range(await locator.count()):
                if await locator.nth(index).is_visible():
                    return True
        except Exception:
            continue
    return False


def _connection_reason(reason: Any) -> str:
    normalized = type(reason).__name__.lower()
    text = str(reason).lower()
    if "refused" in text:
        return "connection_refused"
    if "timed out" in text or "timeout" in text:
        return "connection_timed_out"
    if "name or service" in text or "getaddrinfo" in text:
        return "dns_resolution_failed"
    return normalized or "connection_failed"


_DISCOVERY_SCRIPT = """
() => {
  const controls = Array.from(document.querySelectorAll(
    'input, select, textarea, button, [role="button"]'
  ));
  const normalize = (value) => (value || '').replace(/\\s+/g, ' ').trim().slice(0, 160);
  const labelFor = (element) => {
    if (element.labels && element.labels.length) {
      return normalize(Array.from(element.labels).map((item) => item.innerText).join(' '));
    }
    const aria = element.getAttribute('aria-label');
    if (aria) return normalize(aria);
    const labelledBy = element.getAttribute('aria-labelledby');
    if (labelledBy) {
      return normalize(labelledBy.split(/\\s+/).map((id) => {
        const node = document.getElementById(id);
        return node ? node.innerText : '';
      }).join(' '));
    }
    return normalize(element.placeholder || element.innerText || element.name || element.id);
  };
  const selectorFor = (element, index) => {
    if (element.id) return '#' + CSS.escape(element.id);
    if (element.name) return element.tagName.toLowerCase() + '[name="' + CSS.escape(element.name) + '"]';
    return element.tagName.toLowerCase() + ':nth-of-type(' + (index + 1) + ')';
  };
  return controls.map((element, index) => ({
    tag: element.tagName.toLowerCase(),
    type: (element.getAttribute('type') || '').toLowerCase(),
    id: element.id || null,
    name: element.getAttribute('name') || null,
    label: labelFor(element),
    selector: selectorFor(element, index),
    required: Boolean(element.required),
    disabled: Boolean(element.disabled),
    readonly: Boolean(element.readOnly),
    option_count: element.options ? element.options.length : null
  }));
}
"""


_FIELD_METADATA_SCRIPT = """
(element) => {
  const normalize = (value) => (value || '').replace(/\\s+/g, ' ').trim().slice(0, 160);
  let label = '';
  if (element.labels && element.labels.length) {
    label = Array.from(element.labels).map((item) => item.innerText).join(' ');
  } else {
    label = element.getAttribute('aria-label') || element.placeholder || element.name || element.id;
  }
  return {
    tag: element.tagName.toLowerCase(),
    type: (element.getAttribute('type') || '').toLowerCase(),
    label: normalize(label)
  };
}
"""
