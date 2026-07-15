"""Regression tests for deterministic, human-login-gated page selection."""

from __future__ import annotations

import asyncio

import pytest

from irb_harness.application.page_mapping import sanitize_page_discovery
from irb_harness.infrastructure.browser_session import BrowserController
from irb_harness.infrastructure.contract_loader import load_contract
from irb_harness.infrastructure.web_policy import BrowserPolicyError


class _Element:
    def __init__(self, visible: bool) -> None:
        self.visible = visible

    async def is_visible(self) -> bool:
        return self.visible


class _Locator:
    def __init__(self, visibilities: list[bool]) -> None:
        self.visibilities = visibilities

    async def count(self) -> int:
        return len(self.visibilities)

    def nth(self, index: int) -> _Element:
        return _Element(self.visibilities[index])


class _Page:
    def __init__(self, url: str, selectors: dict[str, list[bool]]) -> None:
        self.url = url
        self.selectors = selectors

    def locator(self, selector: str) -> _Locator:
        return _Locator(self.selectors.get(selector, []))


class _ActionLocator(_Locator):
    def __init__(self) -> None:
        super().__init__([True])
        self.clicked = False

    async def evaluate(self, _script):
        return {"tag": "button", "type": "button", "label": "查詢"}

    async def click(self) -> None:
        self.clicked = True


class _ActionPage(_Page):
    def __init__(self) -> None:
        super().__init__(
            "https://erec.kmuh.org.tw/RECManageSystem/Case/List",
            {"a[href*='Account/Logout']": [True]},
        )
        self.page_title = "案件查詢"
        self.action = _ActionLocator()
        self.controls = [
            {
                "tag": "button",
                "type": "button",
                "id": "Search",
                "name": None,
                "label": "查詢",
                "selector": "#Search",
                "required": False,
                "disabled": False,
                "readonly": False,
                "option_count": None,
            }
        ]

    def locator(self, selector: str):
        if selector == "#Search":
            return self.action
        return super().locator(selector)

    async def title(self) -> str:
        return self.page_title

    async def evaluate(self, _script):
        return [dict(control) for control in self.controls]


class _Context:
    def __init__(self, pages: list[_Page]) -> None:
        self.pages = pages


class _Browser:
    def __init__(self, pages: list[_Page]) -> None:
        self.contexts = [_Context(pages)]


def test_session_status_uses_requested_page_ref_and_ignores_hidden_login_controls(
    monkeypatch,
):
    website = load_contract().website("kmuh_eirb")
    outside = _Page("https://example.org/", {})
    authenticated = _Page(
        "https://erec.kmuh.org.tw/RECManageSystem/Home/Index",
        {
            "#loginForm": [False],
            "#inputUserID": [False],
            "#inputPassword": [False],
            "a[href*='Account/Logout']": [True],
        },
    )
    controller = BrowserController("http://127.0.0.1:9")

    async def connect():
        return _Browser([outside, authenticated])

    monkeypatch.setattr(controller, "connect", connect)
    status = asyncio.run(controller.session_status(website, page_ref="c0p1"))
    wrong_page = asyncio.run(controller.session_status(website, page_ref="c0p0"))

    assert status["status"] == "authenticated"
    assert status["page_ref"] == "c0p1"
    assert wrong_page["status"] == "page_not_open"


def test_visible_login_control_requires_human_login(monkeypatch):
    website = load_contract().website("kmuh_eirb")
    login = _Page(
        "https://erec.kmuh.org.tw/RECManageSystem/Account/Login/",
        {"#loginForm": [True]},
    )
    controller = BrowserController("http://127.0.0.1:9")

    async def connect():
        return _Browser([login])

    monkeypatch.setattr(controller, "connect", connect)
    status = asyncio.run(controller.session_status(website))

    assert status["status"] == "human_login_required"
    assert status["page_ref"] == "c0p0"


def test_reviewed_read_click_rechecks_live_page_fingerprint(monkeypatch):
    website = load_contract().website("kmuh_eirb")
    page = _ActionPage()
    controller = BrowserController("http://127.0.0.1:9")

    async def connect():
        return _Browser([page])

    monkeypatch.setattr(controller, "connect", connect)
    discovery = asyncio.run(controller.discover_current_page(website))
    mapping = sanitize_page_discovery(discovery)
    control_id = mapping["controls"][0]["control_id"]
    monkeypatch.setenv("IRB_WEB_CLICK_MODE", "reviewed")

    result = asyncio.run(
        controller.click_reviewed_control(
            website,
            mapping=mapping,
            control_id=control_id,
            human_confirmed=True,
        )
    )
    assert result["status"] == "reviewed_read_control_clicked"
    assert result["submitted"] is False
    assert page.action.clicked is True

    page.action.clicked = False
    page.page_title = "頁面已變更"
    with pytest.raises(BrowserPolicyError, match="fingerprint differs"):
        asyncio.run(
            controller.click_reviewed_control(
                website,
                mapping=mapping,
                control_id=control_id,
                human_confirmed=True,
            )
        )
    assert page.action.clicked is False
