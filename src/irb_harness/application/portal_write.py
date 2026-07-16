"""Resolve reviewed portal-field bindings before any browser draft write."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping

from irb_harness.application.page_mapping import load_page_mapping
from irb_harness.domain.contracts import (
    ContractRequirement,
    OrganizationContract,
    RequirementKind,
    WebSiteContract,
    WebsiteControlBinding,
)


class PortalWriteError(ValueError):
    """Raised when a draft write is not pinned to one reviewed contract field."""


@dataclass(frozen=True)
class ReviewedPortalWrite:
    """A contract- and artifact-verified draft field target."""

    requirement: ContractRequirement
    website: WebSiteContract
    binding: WebsiteControlBinding
    mapping: Mapping[str, Any]
    value: str


def resolve_reviewed_portal_write(
    contract: OrganizationContract,
    *,
    requirement_id: str,
    site_id: str,
    mapping_sha256: str,
    value: str,
    mapping_root: str | Path = ".irb-web-artifacts",
) -> ReviewedPortalWrite:
    """Prove requirement, binding, mapping, control, and value compatibility."""
    requirements = [
        item for item in contract.requirements if item.requirement_id == requirement_id
    ]
    if len(requirements) != 1:
        raise PortalWriteError(f"requirement must exist exactly once: {requirement_id}")
    requirement = requirements[0]
    if requirement.kind is not RequirementKind.PORTAL_FIELD:
        raise PortalWriteError("only portal_field requirements can be draft-filled")
    if requirement.status == "deprecated":
        raise PortalWriteError("deprecated portal requirements cannot be draft-filled")
    if requirement.website_site_id != site_id:
        raise PortalWriteError("requirement is not bound to the selected site")
    if requirement.page_mapping_sha256 != mapping_sha256:
        raise PortalWriteError(
            "requested mapping SHA-256 does not match the contract requirement"
        )
    if not requirement.control_id:
        raise PortalWriteError("portal requirement is missing a reviewed control_id")

    bindings = [
        item
        for item in contract.website_bindings
        if item.requirement_id == requirement_id
    ]
    if len(bindings) != 1:
        raise PortalWriteError(
            "portal requirement must have exactly one reviewed website binding"
        )
    binding = bindings[0]
    if (
        binding.site_id != site_id
        or binding.page_mapping_sha256 != mapping_sha256
        or binding.control_id != requirement.control_id
    ):
        raise PortalWriteError(
            "reviewed website binding does not match the requested contract field"
        )

    mapping = load_page_mapping(
        organization_id=contract.organization_id,
        site_id=site_id,
        mapping_sha256=mapping_sha256,
        mapping_root=mapping_root,
    )
    controls = mapping.get("controls")
    if not isinstance(controls, list):
        raise PortalWriteError("reviewed page mapping controls are invalid")
    matches = [
        item
        for item in controls
        if isinstance(item, Mapping) and item.get("control_id") == binding.control_id
    ]
    if len(matches) != 1:
        raise PortalWriteError(
            "reviewed control must exist exactly once in the page mapping"
        )
    control = matches[0]
    if control.get("selector") != binding.selector:
        raise PortalWriteError(
            "reviewed binding selector does not match the page mapping"
        )
    if control.get("action_risk") != binding.action_risk.value:
        raise PortalWriteError("reviewed binding risk does not match the page mapping")
    normalized_value = _validate_value(requirement, value, control)
    return ReviewedPortalWrite(
        requirement=requirement,
        website=contract.website(site_id),
        binding=binding,
        mapping=mapping,
        value=normalized_value,
    )


def resolve_legacy_selector_write(
    contract: OrganizationContract,
    *,
    site_id: str,
    selector: str,
    value: str,
    mapping_root: str | Path = ".irb-web-artifacts",
) -> ReviewedPortalWrite:
    """Keep the legacy selector API, but only for one reviewed contract binding."""
    matches = [
        binding
        for binding in contract.website_bindings
        if binding.site_id == site_id and binding.selector == selector
    ]
    if len(matches) != 1:
        raise PortalWriteError(
            "legacy selector writes require exactly one reviewed contract binding"
        )
    binding = matches[0]
    return resolve_reviewed_portal_write(
        contract,
        requirement_id=binding.requirement_id,
        site_id=site_id,
        mapping_sha256=binding.page_mapping_sha256,
        value=value,
        mapping_root=mapping_root,
    )


def _validate_value(
    requirement: ContractRequirement,
    value: str,
    control: Mapping[str, Any],
) -> str:
    if not isinstance(value, str):
        raise PortalWriteError("portal draft values must be strings")
    value_type = requirement.value_type or "string"
    control_type = str(control.get("type") or "").lower()
    control_tag = str(control.get("tag") or "").lower()
    if value_type == "file" or control_type == "file":
        raise PortalWriteError(
            "file uploads require a separate reviewed adapter and are not draft-fillable"
        )
    if value_type == "integer" and not re.fullmatch(r"[+-]?\d+", value.strip()):
        raise PortalWriteError("integer portal values must use base-10 digits")
    if value_type == "number":
        try:
            parsed = Decimal(value.strip())
        except InvalidOperation as exc:
            raise PortalWriteError(
                "number portal values must be decimal numbers"
            ) from exc
        if not parsed.is_finite():
            raise PortalWriteError("number portal values must be finite")
    if value_type == "boolean" or control_type == "checkbox":
        normalized = value.strip().lower()
        if normalized not in {"true", "false"}:
            raise PortalWriteError("boolean portal values must be true or false")
        return normalized
    if value_type == "date":
        try:
            date.fromisoformat(value.strip())
        except ValueError as exc:
            raise PortalWriteError("date portal values must use YYYY-MM-DD") from exc
    if value_type == "choice" and control_tag != "select":
        raise PortalWriteError("choice requirements must bind to a select control")
    if control_tag == "select" and value_type != "choice":
        raise PortalWriteError("select controls require a choice requirement")
    return value
