"""Immutable HTTPS retrieval and safe archive expansion for contract assets."""

from __future__ import annotations

import hashlib
import mimetypes
import os
import re
import shutil
import stat
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen


DEFAULT_MAX_DOWNLOAD_BYTES = 512 * 1024 * 1024
DEFAULT_MAX_ARCHIVE_BYTES = 1024 * 1024 * 1024
DEFAULT_MAX_ARCHIVE_MEMBERS = 1000


class SourceRetrievalError(RuntimeError):
    """Raised when an authoritative asset cannot be retrieved safely."""


class UnsafeArchiveError(SourceRetrievalError):
    """Raised when an archive violates extraction limits or path safety."""


@dataclass(frozen=True)
class RetrievedMember:
    """One immutable regular file expanded from a retrieved archive."""

    relative_path: str
    path: Path
    sha256: str
    byte_size: int

    def manifest_record(self, cache_root: Path) -> dict[str, Any]:
        return {
            "relative_path": self.relative_path,
            "cache_path": str(self.path.relative_to(cache_root)),
            "sha256": self.sha256,
            "byte_size": self.byte_size,
        }


@dataclass(frozen=True)
class RetrievedAsset:
    """A content-addressed response body and optional expanded members."""

    asset_id: str
    requested_url: str
    final_url: str
    media_type: str
    sha256: str
    byte_size: int
    path: Path
    reused: bool
    members: tuple[RetrievedMember, ...] = ()
    acquisition_mode: str = "https_download"
    source_name_sha256: str | None = None
    source_suffix: str | None = None
    human_source_identity_confirmed: bool = False


def retrieve_asset(
    *,
    organization_id: str,
    asset_id: str,
    url: str,
    cache_root: str | Path,
    expected_media_type: str | None = None,
    timeout_seconds: float = 30,
    max_bytes: int = DEFAULT_MAX_DOWNLOAD_BYTES,
    opener: Callable[..., Any] = urlopen,
) -> RetrievedAsset:
    """Retrieve one HTTPS asset into an immutable, content-addressed cache."""
    requested = _validated_https_url(url)
    cache = Path(cache_root).expanduser().resolve()
    partials = cache / ".partial"
    partials.mkdir(parents=True, exist_ok=True)
    request = Request(  # noqa: S310 - HTTPS is enforced before the request
        requested,
        headers={"User-Agent": "irb-harness/1.0 (+citation-ready-source-sync)"},
    )
    temporary_path: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(prefix="download-", dir=partials)
        temporary_path = Path(temporary_name)
        digest = hashlib.sha256()
        byte_size = 0
        with os.fdopen(descriptor, "wb") as output:
            with opener(request, timeout=timeout_seconds) as response:
                status = getattr(response, "status", None)
                if isinstance(status, int) and status >= 400:
                    raise SourceRetrievalError(
                        f"HTTP retrieval failed with status {status}"
                    )
                final_url = _validated_https_url(
                    str(getattr(response, "geturl", lambda: requested)())
                )
                if urlparse(final_url).hostname != urlparse(requested).hostname:
                    raise SourceRetrievalError(
                        "cross-host redirects are not allowed for contract assets"
                    )
                media_type = _response_media_type(response, expected_media_type)
                content_length = _response_content_length(response)
                if content_length is not None and content_length > max_bytes:
                    raise SourceRetrievalError(
                        f"asset exceeds the {max_bytes}-byte retrieval limit"
                    )
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    byte_size += len(chunk)
                    if byte_size > max_bytes:
                        raise SourceRetrievalError(
                            f"asset exceeds the {max_bytes}-byte retrieval limit"
                        )
                    digest.update(chunk)
                    output.write(chunk)
            output.flush()
            os.fsync(output.fileno())

        sha256 = digest.hexdigest()
        suffix = _payload_suffix(final_url, media_type)
        asset_directory = (
            cache
            / _safe_component(organization_id)
            / "assets"
            / _safe_component(asset_id)
            / sha256
        )
        asset_directory.mkdir(parents=True, exist_ok=True)
        payload = asset_directory / f"payload{suffix}"
        reused = payload.exists()
        if reused:
            if _file_sha256(payload) != sha256:
                raise SourceRetrievalError(
                    f"immutable cache entry failed hash verification: {payload}"
                )
        else:
            os.replace(temporary_path, payload)
            temporary_path = None
            payload.chmod(0o600)
        return RetrievedAsset(
            asset_id=asset_id,
            requested_url=requested,
            final_url=final_url,
            media_type=media_type,
            sha256=sha256,
            byte_size=byte_size,
            path=payload,
            reused=reused,
        )
    except SourceRetrievalError:
        raise
    except Exception as exc:
        raise SourceRetrievalError(
            f"failed to retrieve contract asset '{asset_id}': {type(exc).__name__}"
        ) from exc
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def import_local_asset(
    *,
    organization_id: str,
    asset_id: str,
    declared_url: str,
    source_path: str | Path,
    cache_root: str | Path,
    expected_media_type: str | None = None,
    human_source_identity_confirmed: bool = False,
    max_bytes: int = DEFAULT_MAX_DOWNLOAD_BYTES,
) -> RetrievedAsset:
    """Copy a human-confirmed local rendition into the immutable asset cache."""
    requested = _validated_https_url(declared_url)
    provided_source = Path(source_path).expanduser()
    if not human_source_identity_confirmed:
        raise SourceRetrievalError(
            "local import requires explicit human source-identity confirmation"
        )
    if provided_source.is_symlink() or not provided_source.is_file():
        raise SourceRetrievalError("local import source must be a regular file")
    source = provided_source.resolve()
    initial_stat = source.stat()
    if initial_stat.st_size > max_bytes:
        raise SourceRetrievalError(
            f"local asset exceeds the {max_bytes}-byte import limit"
        )
    media_type = _local_media_type(source)
    if not _compatible_media_type(media_type, expected_media_type):
        raise SourceRetrievalError(
            "local asset media type does not match the declared contract asset: "
            f"detected {media_type}, expected {expected_media_type}"
        )

    cache = Path(cache_root).expanduser().resolve()
    partials = cache / ".partial"
    partials.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(prefix="import-", dir=partials)
        temporary_path = Path(temporary_name)
        digest = hashlib.sha256()
        byte_size = 0
        with (
            source.open("rb") as input_handle,
            os.fdopen(descriptor, "wb") as output_handle,
        ):
            while True:
                chunk = input_handle.read(1024 * 1024)
                if not chunk:
                    break
                byte_size += len(chunk)
                if byte_size > max_bytes:
                    raise SourceRetrievalError(
                        f"local asset exceeds the {max_bytes}-byte import limit"
                    )
                digest.update(chunk)
                output_handle.write(chunk)
            output_handle.flush()
            os.fsync(output_handle.fileno())
        final_stat = source.stat()
        stable_identity = (
            initial_stat.st_dev,
            initial_stat.st_ino,
            initial_stat.st_size,
            initial_stat.st_mtime_ns,
        )
        final_identity = (
            final_stat.st_dev,
            final_stat.st_ino,
            final_stat.st_size,
            final_stat.st_mtime_ns,
        )
        if stable_identity != final_identity or byte_size != initial_stat.st_size:
            raise SourceRetrievalError("local import source changed while being copied")

        sha256 = digest.hexdigest()
        suffix = _payload_suffix(source.as_uri(), media_type)
        asset_directory = (
            cache
            / _safe_component(organization_id)
            / "assets"
            / _safe_component(asset_id)
            / sha256
        )
        asset_directory.mkdir(parents=True, exist_ok=True)
        payload = asset_directory / f"payload{suffix}"
        reused = payload.exists()
        if reused:
            if _file_sha256(payload) != sha256:
                raise SourceRetrievalError(
                    f"immutable cache entry failed hash verification: {payload}"
                )
        else:
            os.replace(temporary_path, payload)
            temporary_path = None
            payload.chmod(0o600)
        return RetrievedAsset(
            asset_id=asset_id,
            requested_url=requested,
            final_url=requested,
            media_type=media_type,
            sha256=sha256,
            byte_size=byte_size,
            path=payload,
            reused=reused,
            acquisition_mode="human_provided_local_copy",
            source_name_sha256=hashlib.sha256(source.name.encode("utf-8")).hexdigest(),
            source_suffix=source.suffix.lower() or None,
            human_source_identity_confirmed=True,
        )
    except SourceRetrievalError:
        raise
    except Exception as exc:
        raise SourceRetrievalError(
            f"failed to import local contract asset '{asset_id}': {type(exc).__name__}"
        ) from exc
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def expand_zip_asset(
    asset: RetrievedAsset,
    *,
    cache_root: str | Path,
    max_members: int = DEFAULT_MAX_ARCHIVE_MEMBERS,
    max_total_bytes: int = DEFAULT_MAX_ARCHIVE_BYTES,
) -> RetrievedAsset:
    """Expand a ZIP without traversal, symlinks, overwrites, or unbounded output."""
    if not zipfile.is_zipfile(asset.path):
        raise UnsafeArchiveError(
            f"retrieved asset is not a valid ZIP: {asset.asset_id}"
        )
    cache = Path(cache_root).expanduser().resolve()
    try:
        asset.path.resolve().relative_to(cache)
    except ValueError as exc:
        raise UnsafeArchiveError(
            "archive payload must be inside the source cache"
        ) from exc
    destination = asset.path.parent / "unpacked"
    if destination.is_dir():
        members = _scan_existing_members(destination)
        return _with_members(asset, members)

    temporary = Path(tempfile.mkdtemp(prefix="unpacked-", dir=str(asset.path.parent)))
    try:
        extracted: list[RetrievedMember] = []
        seen_paths: set[str] = set()
        actual_total = 0
        with zipfile.ZipFile(asset.path) as archive:
            infos = archive.infolist()
            regular_infos = [info for info in infos if not info.is_dir()]
            if len(regular_infos) > max_members:
                raise UnsafeArchiveError(
                    f"archive exceeds the {max_members}-member limit"
                )
            declared_total = sum(info.file_size for info in regular_infos)
            if declared_total > max_total_bytes:
                raise UnsafeArchiveError(
                    f"archive exceeds the {max_total_bytes}-byte expansion limit"
                )
            for info in regular_infos:
                relative = _safe_archive_path(info)
                collision_key = relative.casefold()
                if collision_key in seen_paths:
                    raise UnsafeArchiveError(
                        f"archive contains a duplicate path: {relative}"
                    )
                seen_paths.add(collision_key)
                output = temporary.joinpath(*PurePosixPath(relative).parts)
                output.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                byte_size = 0
                with archive.open(info) as source, output.open("xb") as target:
                    while True:
                        chunk = source.read(1024 * 1024)
                        if not chunk:
                            break
                        byte_size += len(chunk)
                        actual_total += len(chunk)
                        if actual_total > max_total_bytes:
                            raise UnsafeArchiveError(
                                f"archive exceeds the {max_total_bytes}-byte expansion limit"
                            )
                        digest.update(chunk)
                        target.write(chunk)
                output.chmod(0o600)
                extracted.append(
                    RetrievedMember(
                        relative_path=relative,
                        path=output,
                        sha256=digest.hexdigest(),
                        byte_size=byte_size,
                    )
                )
        os.replace(temporary, destination)
        temporary = destination
        relocated = tuple(
            RetrievedMember(
                relative_path=member.relative_path,
                path=destination.joinpath(*PurePosixPath(member.relative_path).parts),
                sha256=member.sha256,
                byte_size=member.byte_size,
            )
            for member in extracted
        )
        return _with_members(asset, relocated)
    except UnsafeArchiveError:
        raise
    except Exception as exc:
        raise UnsafeArchiveError(
            f"failed to expand archive '{asset.asset_id}': {type(exc).__name__}"
        ) from exc
    finally:
        if temporary.exists() and temporary != destination:
            shutil.rmtree(temporary, ignore_errors=True)


def _with_members(
    asset: RetrievedAsset, members: tuple[RetrievedMember, ...]
) -> RetrievedAsset:
    return RetrievedAsset(
        asset_id=asset.asset_id,
        requested_url=asset.requested_url,
        final_url=asset.final_url,
        media_type=asset.media_type,
        sha256=asset.sha256,
        byte_size=asset.byte_size,
        path=asset.path,
        reused=asset.reused,
        members=members,
        acquisition_mode=asset.acquisition_mode,
        source_name_sha256=asset.source_name_sha256,
        source_suffix=asset.source_suffix,
        human_source_identity_confirmed=asset.human_source_identity_confirmed,
    )


def _validated_https_url(value: str) -> str:
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise SourceRetrievalError(
            "contract asset URL must be absolute HTTPS without embedded credentials"
        )
    return value


def _response_media_type(response: Any, expected: str | None) -> str:
    headers = getattr(response, "headers", None)
    if headers is not None and hasattr(headers, "get_content_type"):
        actual = str(headers.get_content_type()).lower()
    elif headers is not None:
        actual = str(headers.get("Content-Type", "")).split(";", 1)[0].lower()
    else:
        actual = ""
    return actual or expected or "application/octet-stream"


def _response_content_length(response: Any) -> int | None:
    headers = getattr(response, "headers", None)
    raw = headers.get("Content-Length") if headers is not None else None
    if raw is None:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def _local_media_type(source: Path) -> str:
    with source.open("rb") as handle:
        prefix = handle.read(4096)
    if prefix.startswith(b"%PDF-"):
        return "application/pdf"
    if zipfile.is_zipfile(source):
        with zipfile.ZipFile(source) as archive:
            names = set(archive.namelist())
        if {"[Content_Types].xml", "word/document.xml"} <= names:
            return (
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            )
        return "application/zip"
    normalized = prefix.lstrip().lower()
    if normalized.startswith(b"<!doctype html") or normalized.startswith(b"<html"):
        return "text/html"
    if source.suffix.lower() in {".md", ".markdown"}:
        return "text/markdown"
    if source.suffix.lower() in {".yml", ".yaml"}:
        return "application/yaml"
    if source.suffix.lower() in {".docx", ".pdf", ".zip"}:
        return "application/octet-stream"
    return mimetypes.guess_type(source.name)[0] or "application/octet-stream"


def _compatible_media_type(actual: str, expected: str | None) -> bool:
    if not expected or expected == "application/octet-stream":
        return True
    aliases = {
        "application/x-zip-compressed": "application/zip",
        "text/x-markdown": "text/markdown",
    }
    return aliases.get(actual, actual) == aliases.get(
        expected.lower(), expected.lower()
    )


def _payload_suffix(url: str, media_type: str) -> str:
    candidate = Path(unquote(urlparse(url).path)).suffix.lower()
    known = {
        ".csv",
        ".docx",
        ".htm",
        ".html",
        ".json",
        ".md",
        ".pdf",
        ".txt",
        ".yaml",
        ".yml",
        ".zip",
    }
    if candidate in known:
        return candidate
    return {
        "application/json": ".json",
        "application/pdf": ".pdf",
        "application/zip": ".zip",
        "application/x-zip-compressed": ".zip",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "text/csv": ".csv",
        "text/html": ".html",
        "text/markdown": ".md",
        "text/plain": ".txt",
    }.get(media_type, ".bin")


def _safe_component(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-")
    if not normalized:
        normalized = "asset"
    if normalized != value:
        normalized = f"{normalized}-{hashlib.sha256(value.encode()).hexdigest()[:10]}"
    return normalized


def _safe_archive_path(info: zipfile.ZipInfo) -> str:
    raw = info.filename.replace("\\", "/")
    path = PurePosixPath(raw)
    mode = (info.external_attr >> 16) & 0xFFFF
    if stat.S_ISLNK(mode):
        raise UnsafeArchiveError(f"archive symlink is not allowed: {raw}")
    if (
        not raw
        or raw.startswith("/")
        or any(part in {"", ".", ".."} for part in path.parts)
        or any(":" in part or "\x00" in part for part in path.parts)
    ):
        raise UnsafeArchiveError(f"unsafe archive member path: {raw}")
    return path.as_posix()


def _scan_existing_members(directory: Path) -> tuple[RetrievedMember, ...]:
    members: list[RetrievedMember] = []
    for path in sorted(item for item in directory.rglob("*") if item.is_file()):
        members.append(
            RetrievedMember(
                relative_path=path.relative_to(directory).as_posix(),
                path=path,
                sha256=_file_sha256(path),
                byte_size=path.stat().st_size,
            )
        )
    return tuple(members)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
