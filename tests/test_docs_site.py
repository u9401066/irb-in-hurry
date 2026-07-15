"""Regression checks for the dependency-free GitHub Pages documentation site."""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class _SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.asset_paths: list[str] = []
        self.lang: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "html":
            self.lang = values.get("lang")
        if values.get("id"):
            self.ids.add(str(values["id"]))
        for key in ("href", "src"):
            value = values.get(key)
            if value:
                self.asset_paths.append(value)


def test_docs_site_has_accessible_core_sections_and_relative_assets():
    parser = _SiteParser()
    parser.feed((ROOT / "site" / "index.html").read_text(encoding="utf-8"))

    assert parser.lang == "zh-Hant"
    assert {"main", "architecture", "kmuh", "browser-mcp", "quickstart"} <= (parser.ids)
    assert "styles.css" in parser.asset_paths
    assert not any(path.startswith("/") for path in parser.asset_paths)


def test_pages_workflow_uses_official_artifact_deployment_actions():
    workflow = (ROOT / ".github" / "workflows" / "pages.yml").read_text(
        encoding="utf-8"
    )

    assert "actions/configure-pages@v5" in workflow
    assert "actions/upload-pages-artifact@v4" in workflow
    assert "actions/deploy-pages@v4" in workflow
    assert "path: site" in workflow
    assert "pages: write" in workflow
    assert "id-token: write" in workflow


def test_ci_workflow_checks_supported_python_and_locked_dependencies():
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert '"3.10"' in workflow
    assert '"3.12"' in workflow
    assert "uv sync --locked --group dev" in workflow
    assert "ruff check src/irb_harness scripts/report_kmuh.py tests/" in workflow
    assert "mypy src --ignore-missing-imports" in workflow
    assert "pytest tests/ -q" in workflow
    assert "uv build" in workflow
