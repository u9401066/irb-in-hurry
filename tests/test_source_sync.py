"""Regression tests for immutable official-source synchronization."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from email.message import Message
from pathlib import Path
from typing import Any

import pytest
import yaml

from irb_harness.application.evidence_mapping import (
    EvidenceMappingError,
    map_workflow_evidence,
)
from irb_harness.application.source_sync import sync_contract_sources
from irb_harness.infrastructure.contract_loader import load_contract_mapping
from irb_harness.infrastructure.document_ingest import ingest_document
from irb_harness.infrastructure.source_archive import (
    RetrievedAsset,
    SourceRetrievalError,
    UnsafeArchiveError,
    expand_zip_asset,
    retrieve_asset,
)


class _Response(io.BytesIO):
    def __init__(
        self, payload: bytes, *, url: str, media_type: str = "text/html"
    ) -> None:
        super().__init__(payload)
        self.status = 200
        self._url = url
        self.headers = Message()
        self.headers["Content-Type"] = f"{media_type}; charset=utf-8"
        self.headers["Content-Length"] = str(len(payload))

    def geturl(self) -> str:
        return self._url

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()


def test_retrieve_asset_is_https_content_addressed_and_reusable(tmp_path):
    payload = b"<html><body>KMUH source</body></html>"

    def opener(_request, *, timeout):
        assert timeout == 30
        return _Response(payload, url="https://example.org/source")

    first = retrieve_asset(
        organization_id="example",
        asset_id="official_page",
        url="https://example.org/source",
        cache_root=tmp_path,
        opener=opener,
    )
    second = retrieve_asset(
        organization_id="example",
        asset_id="official_page",
        url="https://example.org/source",
        cache_root=tmp_path,
        opener=opener,
    )

    assert first.sha256 == hashlib.sha256(payload).hexdigest()
    assert first.path.read_bytes() == payload
    assert first.reused is False
    assert second.path == first.path
    assert second.reused is True


def test_retrieve_asset_rejects_cross_host_redirect(tmp_path):
    def opener(_request, *, timeout):
        del timeout
        return _Response(b"x", url="https://other.example/source")

    with pytest.raises(SourceRetrievalError, match="cross-host"):
        retrieve_asset(
            organization_id="example",
            asset_id="official_page",
            url="https://example.org/source",
            cache_root=tmp_path,
            opener=opener,
        )


def test_zip_expansion_rejects_path_traversal(tmp_path):
    archive_path = tmp_path / "payload.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("../escape.txt", "unsafe")
    payload = archive_path.read_bytes()
    asset = RetrievedAsset(
        asset_id="forms",
        requested_url="https://example.org/forms.zip",
        final_url="https://example.org/forms.zip",
        media_type="application/zip",
        sha256=hashlib.sha256(payload).hexdigest(),
        byte_size=len(payload),
        path=archive_path,
        reused=False,
    )

    with pytest.raises(UnsafeArchiveError, match="unsafe archive member"):
        expand_zip_asset(asset, cache_root=tmp_path)

    assert not (tmp_path.parent / "escape.txt").exists()


def test_source_sync_writes_evidence_and_never_marks_download_as_verified(tmp_path):
    contract = load_contract_mapping()
    cache = tmp_path / "cache"
    target = tmp_path / "organizations" / "kmuh" / "contract.yml"

    def retriever(**kwargs):
        payload = b"<html><body><h1>Official guidance</h1><script>secret</script></body></html>"
        digest = hashlib.sha256(payload).hexdigest()
        path = (
            Path(kwargs["cache_root"])
            / "kmuh"
            / "assets"
            / kwargs["asset_id"]
            / digest
            / "payload.html"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return RetrievedAsset(
            asset_id=kwargs["asset_id"],
            requested_url=kwargs["url"],
            final_url=kwargs["url"],
            media_type="text/html",
            sha256=digest,
            byte_size=len(payload),
            path=path,
            reused=False,
        )

    result = sync_contract_sources(
        contract,
        output_path=target,
        cache_root=cache,
        source_ids=["kmuh_sop_02_01"],
        retriever=retriever,
    )

    updated = yaml.safe_load(result.contract_path.read_text(encoding="utf-8"))
    source = next(
        item
        for item in updated["source_documents"]
        if item["source_id"] == "kmuh_sop_02_01"
    )
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    evidence = manifest["assets"][0]["documents"][0]["evidence"]
    assert source["evidence_status"] == "retrieved_needs_rule_mapping"
    assert len(source["sha256"]) == 64
    intake = next(
        item
        for item in updated["workflow"]["transitions"]
        if item["event"] == "administrative_intake"
    )
    assert intake["evidence_refs"][0]["locator_status"] == "needs_mapping"
    checklist = next(
        item
        for item in updated["requirements"]
        if item["requirement_id"] == "kmuh_new_submission_checklist"
    )
    sop_reference = next(
        item
        for item in checklist["evidence_refs"]
        if item["source_document_id"] == "kmuh_sop_02_01"
    )
    assert sop_reference["locator_status"] == "needs_mapping"
    assert evidence["spans"][0]["context"] == "Official guidance"
    assert all("secret" not in span["context"] for span in evidence["spans"])
    assert result.failed_ids == ()

    mapped_path = tmp_path / "mapped.yml"
    span_id = evidence["spans"][0]["span_id"]
    map_workflow_evidence(
        updated,
        evidence_manifest_path=result.manifest_path,
        transition_event="administrative_intake",
        source_document_id="kmuh_sop_02_01",
        span_ids=[span_id],
        output_path=mapped_path,
        cache_root=cache,
    )
    mapped = yaml.safe_load(mapped_path.read_text(encoding="utf-8"))
    mapped_intake = next(
        item
        for item in mapped["workflow"]["transitions"]
        if item["event"] == "administrative_intake"
    )
    assert mapped_intake["evidence_refs"][0]["locator_status"] == "verified"
    assert mapped_intake["evidence_refs"][0]["span_ids"] == [span_id]
    assert mapped["evidence_bindings"][0]["evidence_manifest_sha256"]

    with pytest.raises(EvidenceMappingError, match="absent"):
        map_workflow_evidence(
            updated,
            evidence_manifest_path=result.manifest_path,
            transition_event="administrative_intake",
            source_document_id="kmuh_sop_02_01",
            span_ids=["missing:L999"],
            output_path=tmp_path / "invalid.yml",
            cache_root=cache,
        )

    target.write_text("user-owned: true\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        sync_contract_sources(
            contract,
            output_path=target,
            cache_root=cache,
            source_ids=["kmuh_sop_02_01"],
            retriever=retriever,
        )

    sync_contract_sources(
        contract,
        output_path=target,
        cache_root=cache,
        source_ids=["kmuh_sop_02_01"],
        update_output=True,
        retriever=retriever,
    )
    snapshots = list((cache / "kmuh" / "contract-snapshots").glob("*.yml"))
    assert len(snapshots) == 1
    assert snapshots[0].read_text(encoding="utf-8") == "user-owned: true\n"


def test_html_ingest_excludes_non_visible_script_and_style_text(tmp_path):
    source = tmp_path / "official.html"
    source.write_text(
        "<h1>公開指引</h1><style>.hidden{}</style><script>token</script><p>送審流程</p>",
        encoding="utf-8",
    )

    ingested = ingest_document(source, institution_id="kmuh")

    contexts = [span.context for span in ingested.spans]
    assert contexts == ["公開指引", "送審流程"]
