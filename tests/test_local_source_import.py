"""Regression tests for human-confirmed offline contract-asset imports."""

from __future__ import annotations

import hashlib
import json
import stat
import zipfile

import pytest
import yaml

from irb_harness.application.evidence_mapping import map_workflow_evidence
from irb_harness.application.source_sync import (
    SourceSyncError,
    import_contract_asset,
)
from irb_harness.infrastructure.contract_loader import load_contract_mapping
from irb_harness.infrastructure.source_archive import (
    SourceRetrievalError,
    import_local_asset,
)


def _kmuh_contract_with_html_sop():
    contract = load_contract_mapping()
    source = next(
        item
        for item in contract["source_documents"]
        if item["source_id"] == "kmuh_sop_02_01"
    )
    source["media_type"] = "text/html"
    return contract


def test_local_source_import_is_immutable_private_and_mapping_compatible(tmp_path):
    source = tmp_path / "KMUH-SOP-02-01.html"
    source.write_text(
        "<h1>新案送審程序</h1><script>private-token</script><p>行政審查</p>",
        encoding="utf-8",
    )
    original_bytes = source.read_bytes()
    contract = _kmuh_contract_with_html_sop()
    cache = tmp_path / "cache"
    output = tmp_path / "organizations" / "kmuh" / "contract.yml"

    with pytest.raises(SourceSyncError, match="human source-identity confirmation"):
        import_contract_asset(
            contract,
            local_file=source,
            source_id="kmuh_sop_02_01",
            output_path=output,
            cache_root=cache,
        )

    result = import_contract_asset(
        contract,
        local_file=source,
        source_id="kmuh_sop_02_01",
        output_path=output,
        cache_root=cache,
        human_source_identity_confirmed=True,
    )

    assert source.read_bytes() == original_bytes
    raw_manifest = result.manifest_path.read_text(encoding="utf-8")
    assert str(source.resolve()) not in raw_manifest
    manifest = json.loads(raw_manifest)
    asset = manifest["assets"][0]
    assert asset["acquisition_mode"] == "human_provided_local_copy"
    assert asset["source_identity_confirmation"] == "human_confirmed"
    assert (
        asset["source_name_sha256"]
        == hashlib.sha256(source.name.encode("utf-8")).hexdigest()
    )
    assert asset["source_suffix"] == ".html"
    evidence = asset["documents"][0]["evidence"]
    contexts = [span["context"] for span in evidence["spans"]]
    assert contexts == ["新案送審程序", "行政審查"]
    assert all("private-token" not in context for context in contexts)

    updated = yaml.safe_load(output.read_text(encoding="utf-8"))
    updated_source = next(
        item
        for item in updated["source_documents"]
        if item["source_id"] == "kmuh_sop_02_01"
    )
    assert updated_source["retrieval"]["acquisition_mode"] == (
        "human_provided_local_copy"
    )
    assert updated_source["retrieval"]["source_identity_confirmation"] == (
        "human_confirmed"
    )
    cached = cache / updated_source["retrieval"]["cache_path"]
    assert cached.read_bytes() == original_bytes
    assert stat.S_IMODE(cached.stat().st_mode) == 0o600

    span_id = evidence["spans"][0]["span_id"]
    mapped_path = tmp_path / "mapped.yml"
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
    transition = next(
        item
        for item in mapped["workflow"]["transitions"]
        if item["event"] == "administrative_intake"
    )
    assert transition["evidence_refs"][0]["locator_status"] == "verified"


def test_local_import_rejects_media_mismatch_and_symlinks(tmp_path):
    source = tmp_path / "not-a-pdf.txt"
    source.write_text("not an official PDF", encoding="utf-8")
    link = tmp_path / "linked.txt"
    link.symlink_to(source)
    renamed_pdf = tmp_path / "renamed.pdf"
    renamed_pdf.write_text("still not a PDF", encoding="utf-8")

    with pytest.raises(SourceRetrievalError, match="media type does not match"):
        import_local_asset(
            organization_id="kmuh",
            asset_id="kmuh_sop_02_01",
            declared_url="https://example.org/sop.pdf",
            source_path=source,
            cache_root=tmp_path / "cache",
            expected_media_type="application/pdf",
            human_source_identity_confirmed=True,
        )

    with pytest.raises(SourceRetrievalError, match="regular file"):
        import_local_asset(
            organization_id="kmuh",
            asset_id="kmuh_sop_02_01",
            declared_url="https://example.org/source.txt",
            source_path=link,
            cache_root=tmp_path / "cache",
            expected_media_type="text/plain",
            human_source_identity_confirmed=True,
        )

    with pytest.raises(SourceRetrievalError, match="media type does not match"):
        import_local_asset(
            organization_id="kmuh",
            asset_id="kmuh_sop_02_01",
            declared_url="https://example.org/sop.pdf",
            source_path=renamed_pdf,
            cache_root=tmp_path / "cache",
            expected_media_type="application/pdf",
            human_source_identity_confirmed=True,
        )


def test_local_import_requires_explicit_revision_and_records_superseded_hash(tmp_path):
    first = tmp_path / "first.html"
    first.write_text("<html><body>第一版程序</body></html>", encoding="utf-8")
    second = tmp_path / "second.html"
    second.write_text("<html><body>第二版程序</body></html>", encoding="utf-8")
    cache = tmp_path / "cache"
    output = tmp_path / "contract.yml"

    initial = import_contract_asset(
        _kmuh_contract_with_html_sop(),
        local_file=first,
        source_id="kmuh_sop_02_01",
        output_path=output,
        cache_root=cache,
        human_source_identity_confirmed=True,
    )
    initial_contract = yaml.safe_load(output.read_text(encoding="utf-8"))
    initial_sha = json.loads(initial.manifest_path.read_text(encoding="utf-8"))[
        "assets"
    ][0]["byte_sha256"]

    with pytest.raises(SourceSyncError, match="allow_revision is required"):
        import_contract_asset(
            initial_contract,
            local_file=second,
            source_id="kmuh_sop_02_01",
            output_path=output,
            cache_root=cache,
            human_source_identity_confirmed=True,
            update_output=True,
        )

    revised = import_contract_asset(
        initial_contract,
        local_file=second,
        source_id="kmuh_sop_02_01",
        output_path=output,
        cache_root=cache,
        human_source_identity_confirmed=True,
        allow_revision=True,
        update_output=True,
    )
    revised_contract = yaml.safe_load(output.read_text(encoding="utf-8"))
    revised_source = next(
        item
        for item in revised_contract["source_documents"]
        if item["source_id"] == "kmuh_sop_02_01"
    )
    revised_manifest = json.loads(revised.manifest_path.read_text(encoding="utf-8"))
    assert revised_source["retrieval"]["supersedes_sha256"] == initial_sha
    assert revised_manifest["assets"][0]["supersedes_contract_sha256"] == initial_sha
    snapshots = list((cache / "kmuh" / "contract-snapshots").glob("*.yml"))
    assert snapshots


def test_local_form_set_zip_uses_safe_expansion_and_evidence_manifest(tmp_path):
    archive = tmp_path / "official-forms.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("instructions.txt", "新案表單填寫說明")
    output = tmp_path / "contract.yml"

    result = import_contract_asset(
        load_contract_mapping(),
        local_file=archive,
        form_set_id="kmuh_general_new",
        output_path=output,
        cache_root=tmp_path / "cache",
        human_source_identity_confirmed=True,
    )

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    asset = manifest["assets"][0]
    assert asset["contract_collection"] == "form_sets"
    assert asset["documents"][0]["relative_path"] == "instructions.txt"
    assert asset["documents"][0]["evidence"]["spans"][0]["context"] == (
        "新案表單填寫說明"
    )
    contract = yaml.safe_load(output.read_text(encoding="utf-8"))
    form_set = next(
        item
        for item in contract["form_sets"]
        if item["form_set_id"] == "kmuh_general_new"
    )
    assert form_set["evidence_status"] == "retrieved_needs_rule_mapping"
