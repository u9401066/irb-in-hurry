"""Pure safety and redaction policy for eIRB browser operations."""

from __future__ import annotations

import hashlib
import re
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from irb_harness.domain.contracts import ActionRisk, WebSiteContract


SUBMIT_TERMS = ("送出", "提交", "申請", "簽署", "核准", "confirm", "submit", "approve")
DESTRUCTIVE_TERMS = ("刪除", "撤案", "終止", "作廢", "delete", "remove", "terminate")
DRAFT_TERMS = (
    "儲存",
    "暫存",
    "更新",
    "上傳",
    "新增",
    "建立",
    "編輯",
    "修改",
    "save",
    "update",
    "upload",
    "add",
    "create",
    "edit",
)


class BrowserPolicyError(RuntimeError):
    """Raised when a browser operation violates the organization contract."""


def assert_allowed_url(url: str, website: WebSiteContract) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise BrowserPolicyError("only absolute HTTPS URLs are allowed")
    host = parsed.hostname.lower()
    if host not in {allowed.lower() for allowed in website.allowed_hosts}:
        raise BrowserPolicyError(
            f"host is not allowed for site '{website.site_id}': {host}"
        )


def redact_url(url: str) -> str:
    """Preserve route shape while suppressing identifiers and query values."""
    parsed = urlparse(url)
    redacted_query = urlencode(
        [
            (key, "<redacted>")
            for key, _ in parse_qsl(parsed.query, keep_blank_values=True)
        ]
    )
    return urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, "", redacted_query, "")
    )


def classify_action(label: str, *, element_type: str = "") -> ActionRisk:
    normalized = " ".join(f"{label} {element_type}".lower().split())
    if _contains_any(normalized, DESTRUCTIVE_TERMS):
        return ActionRisk.DESTRUCTIVE
    if _contains_any(normalized, SUBMIT_TERMS) or element_type.lower() == "submit":
        return ActionRisk.SUBMIT
    if _contains_any(normalized, DRAFT_TERMS):
        return ActionRisk.DRAFT_WRITE
    return ActionRisk.READ


def classify_control(
    label: str,
    *,
    tag: str = "",
    element_type: str = "",
) -> ActionRisk:
    """Classify fields as draft writes without treating their labels as actions."""
    normalized_tag = tag.lower()
    normalized_type = element_type.lower()
    if normalized_tag in {"select", "textarea"}:
        return ActionRisk.DRAFT_WRITE
    if normalized_tag == "input" and normalized_type not in {
        "button",
        "image",
        "reset",
        "submit",
    }:
        return ActionRisk.DRAFT_WRITE
    return classify_action(label, element_type=element_type)


def page_fingerprint(url: str, title: str, control_labels: Iterable[str]) -> str:
    normalized_labels = [re.sub(r"\s+", " ", label).strip() for label in control_labels]
    material = "\n".join([redact_url(url), title.strip(), *normalized_labels])
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _contains_any(value: str, terms: Iterable[str]) -> bool:
    return any(term in value for term in terms)
