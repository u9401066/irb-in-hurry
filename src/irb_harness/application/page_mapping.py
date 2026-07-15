"""Create value-free, reviewable browser page mapping artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Mapping


class PageMappingError(ValueError):
    """Raised when discovery output is unsafe or structurally invalid."""


_FORBIDDEN_KEYS = {
    "body",
    "html",
    "inner_html",
    "outer_html",
    "page_source",
    "text_content",
    "value",
    "values",
}


def sanitize_page_discovery(discovery: Mapping[str, Any]) -> dict[str, Any]:
    """Remove raw labels and reject any discovery payload containing field values."""
    if discovery.get("values_included") is not False:
        raise PageMappingError(
            "discovery must explicitly declare values_included=false"
        )
    _reject_forbidden_keys(discovery)
    site_id = _required_string(discovery, "site_id")
    page_fingerprint = _sha256_string(discovery, "page_fingerprint")
    url = _required_string(discovery, "url")
    controls_raw = discovery.get("controls")
    if not isinstance(controls_raw, list):
        raise PageMappingError("controls must be a list")

    controls: list[dict[str, Any]] = []
    seen_selectors: set[str] = set()
    for index, raw in enumerate(controls_raw):
        if not isinstance(raw, Mapping):
            raise PageMappingError(f"control {index} must be a mapping")
        selector = _required_string(raw, "selector")
        if len(selector) > 300 or any(character in selector for character in "\r\n"):
            raise PageMappingError(f"control {index} has an unsafe selector")
        if selector in seen_selectors:
            raise PageMappingError(f"duplicate control selector: {selector}")
        seen_selectors.add(selector)
        label = str(raw.get("label") or "")
        label_sha256 = hashlib.sha256(label.encode("utf-8")).hexdigest()
        control_material = "\n".join(
            [page_fingerprint, selector, str(raw.get("tag") or ""), label_sha256]
        )
        controls.append(
            {
                "control_id": hashlib.sha256(
                    control_material.encode("utf-8")
                ).hexdigest()[:20],
                "selector": selector,
                "tag": str(raw.get("tag") or ""),
                "type": str(raw.get("type") or ""),
                "label_sha256": label_sha256,
                "label_length": len(label),
                "required": bool(raw.get("required", False)),
                "disabled": bool(raw.get("disabled", False)),
                "readonly": bool(raw.get("readonly", False)),
                "option_count": _optional_nonnegative_int(raw.get("option_count")),
                "action_risk": str(raw.get("action_risk") or "read"),
            }
        )
    mapping: dict[str, Any] = {
        "schema_version": "1.0",
        "site_id": site_id,
        "url": url,
        "title_sha256": _sha256_string(discovery, "title_sha256"),
        "title_length": _nonnegative_int(discovery.get("title_length"), "title_length"),
        "page_fingerprint": page_fingerprint,
        "control_count": len(controls),
        "controls": controls,
        "privacy": {
            "field_values_included": False,
            "raw_labels_included": False,
            "page_body_included": False,
        },
    }
    mapping["mapping_sha256"] = _mapping_sha256(mapping)
    return mapping


def write_page_mapping(
    discovery: Mapping[str, Any],
    output_path: str | Path,
    *,
    force: bool = False,
) -> tuple[Path, dict[str, Any]]:
    """Atomically write a sanitized JSON mapping, refusing implicit overwrite."""
    mapping = sanitize_page_discovery(discovery)
    target = Path(output_path).expanduser().resolve()
    payload = (
        json.dumps(mapping, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    if target.exists() and target.read_bytes() != payload and not force:
        raise FileExistsError(f"refusing to overwrite existing page mapping: {target}")
    if not target.exists() or target.read_bytes() != payload:
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.", dir=target.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    return target, mapping


def load_page_mapping(
    *,
    organization_id: str,
    site_id: str,
    mapping_sha256: str,
    mapping_root: str | Path = ".irb-web-artifacts",
) -> dict[str, Any]:
    """Load one content-addressed mapping without accepting arbitrary file paths."""
    for value, label in (
        (organization_id, "organization_id"),
        (site_id, "site_id"),
    ):
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", value):
            raise PageMappingError(f"{label} must be a filesystem-safe identifier")
    _validate_digest(mapping_sha256, "mapping_sha256")
    path = (
        Path(mapping_root).expanduser().resolve()
        / organization_id
        / site_id
        / f"{mapping_sha256}.json"
    )
    if not path.is_file():
        raise FileNotFoundError(f"reviewed page mapping not found: {mapping_sha256}")
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PageMappingError("page mapping is not valid JSON") from exc
    if not isinstance(loaded, Mapping):
        raise PageMappingError("page mapping root must be a mapping")
    mapping = dict(loaded)
    validate_page_mapping(mapping)
    if mapping["mapping_sha256"] != mapping_sha256:
        raise PageMappingError("requested mapping SHA-256 does not match the artifact")
    if mapping["site_id"] != site_id:
        raise PageMappingError("page mapping site_id does not match the requested site")
    return mapping


def validate_page_mapping(mapping: Mapping[str, Any]) -> None:
    """Verify artifact integrity, privacy declarations, and control identities."""
    _reject_forbidden_keys(mapping, path="mapping")
    if "label" in mapping:
        raise PageMappingError("page mapping must not contain raw labels")
    digest = _sha256_string(mapping, "mapping_sha256")
    unsigned = dict(mapping)
    del unsigned["mapping_sha256"]
    if _mapping_sha256(unsigned) != digest:
        raise PageMappingError("page mapping SHA-256 verification failed")
    _required_string(mapping, "site_id")
    _required_string(mapping, "url")
    _sha256_string(mapping, "title_sha256")
    _sha256_string(mapping, "page_fingerprint")
    controls = mapping.get("controls")
    if not isinstance(controls, list):
        raise PageMappingError("page mapping controls must be a list")
    if _nonnegative_int(mapping.get("control_count"), "control_count") != len(controls):
        raise PageMappingError("page mapping control_count does not match controls")
    privacy = mapping.get("privacy")
    if not isinstance(privacy, Mapping) or any(
        privacy.get(key) is not False
        for key in (
            "field_values_included",
            "raw_labels_included",
            "page_body_included",
        )
    ):
        raise PageMappingError("page mapping privacy declarations must all be false")
    control_ids: set[str] = set()
    selectors: set[str] = set()
    for index, control in enumerate(controls):
        if not isinstance(control, Mapping):
            raise PageMappingError(f"mapped control {index} must be a mapping")
        if "label" in control:
            raise PageMappingError("page mapping must not contain raw labels")
        control_id = _required_string(control, "control_id")
        selector = _required_string(control, "selector")
        _sha256_string(control, "label_sha256")
        if control_id in control_ids or selector in selectors:
            raise PageMappingError("page mapping contains duplicate control identity")
        control_ids.add(control_id)
        selectors.add(selector)
        if control.get("action_risk") not in {
            "read",
            "draft_write",
            "submit",
            "destructive",
        }:
            raise PageMappingError(f"mapped control {index} has unknown action_risk")


def _reject_forbidden_keys(value: Any, path: str = "discovery") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized = str(key).lower()
            if normalized in _FORBIDDEN_KEYS and normalized != "values_included":
                raise PageMappingError(f"forbidden sensitive field at {path}.{key}")
            _reject_forbidden_keys(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_forbidden_keys(nested, f"{path}[{index}]")


def _mapping_sha256(mapping: Mapping[str, Any]) -> str:
    payload = json.dumps(
        mapping, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _required_string(value: Mapping[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise PageMappingError(f"{key} must be a non-empty string")
    return result


def _sha256_string(value: Mapping[str, Any], key: str) -> str:
    result = _required_string(value, key)
    if len(result) != 64 or any(
        character not in "0123456789abcdef" for character in result
    ):
        raise PageMappingError(f"{key} must be a lowercase SHA-256 digest")
    return result


def _nonnegative_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise PageMappingError(f"{label} must be a non-negative integer")
    return value


def _optional_nonnegative_int(value: Any) -> int | None:
    if value is None:
        return None
    return _nonnegative_int(value, "option_count")


def _validate_digest(value: str, label: str) -> None:
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise PageMappingError(f"{label} must be a lowercase SHA-256 digest")
