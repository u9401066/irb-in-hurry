"""Bind portal-field requirements to reviewed, content-addressed page controls."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from irb_harness.application.evidence_mapping import write_contract_mapping
from irb_harness.application.page_mapping import load_page_mapping
from irb_harness.domain.contracts import OrganizationContract, RequirementKind


class WebsiteBindingError(ValueError):
    """Raised when a portal requirement cannot be safely bound to a control."""


@dataclass(frozen=True)
class WebsiteBindingResult:
    contract_path: Path
    requirement_id: str
    site_id: str
    mapping_sha256: str
    control_id: str


def bind_requirement_to_control(
    contract_mapping: Mapping[str, Any],
    *,
    requirement_id: str,
    site_id: str,
    mapping_sha256: str,
    control_id: str,
    output_path: str | Path,
    mapping_root: str | Path = ".irb-web-artifacts",
    cache_root: str | Path = ".irb-source-cache",
    replace_binding: bool = False,
    update_output: bool = False,
) -> WebsiteBindingResult:
    """Verify a sanitized mapping and bind one non-submit field control."""
    original = deepcopy(dict(contract_mapping))
    contract = OrganizationContract.from_mapping(original)
    requirements = [
        item for item in contract.requirements if item.requirement_id == requirement_id
    ]
    if len(requirements) != 1:
        raise WebsiteBindingError(
            f"requirement must exist exactly once: {requirement_id}"
        )
    requirement = requirements[0]
    if requirement.kind is not RequirementKind.PORTAL_FIELD:
        raise WebsiteBindingError("only portal_field requirements can be bound")
    if not requirement.data_path:
        raise WebsiteBindingError(
            "portal_field requirement must declare a data_path before binding"
        )
    if requirement.website_site_id and not replace_binding:
        raise WebsiteBindingError(
            "requirement already has a website binding; replace_binding is required"
        )

    mapping = load_page_mapping(
        organization_id=contract.organization_id,
        site_id=site_id,
        mapping_sha256=mapping_sha256,
        mapping_root=mapping_root,
    )
    controls = mapping.get("controls", [])
    matches = [
        item
        for item in controls
        if isinstance(item, Mapping) and item.get("control_id") == control_id
    ]
    if len(matches) != 1:
        raise WebsiteBindingError(
            "control_id must exist exactly once in the reviewed mapping"
        )
    control = matches[0]
    if control.get("tag") not in {"input", "select", "textarea"}:
        raise WebsiteBindingError("portal requirement must bind to a field control")
    if control.get("type") in {"hidden", "password", "submit", "button"}:
        raise WebsiteBindingError(
            f"field control type cannot be bound: {control.get('type')}"
        )
    if control.get("disabled") is True:
        raise WebsiteBindingError("disabled field controls cannot be bound")
    if control.get("action_risk") in {"submit", "destructive"}:
        raise WebsiteBindingError("submit or destructive controls cannot be bound")

    raw_requirements = original.get("requirements")
    if not isinstance(raw_requirements, list):
        raise WebsiteBindingError("contract requirements must be a list")
    raw_matches = [
        item
        for item in raw_requirements
        if isinstance(item, dict) and item.get("requirement_id") == requirement_id
    ]
    if len(raw_matches) != 1:
        raise WebsiteBindingError(
            f"raw requirement must exist exactly once: {requirement_id}"
        )
    raw_requirement = raw_matches[0]
    raw_requirement["website_site_id"] = site_id
    raw_requirement["page_mapping_sha256"] = mapping_sha256
    raw_requirement["control_id"] = control_id

    bindings = original.setdefault("website_bindings", [])
    if not isinstance(bindings, list):
        raise WebsiteBindingError("contract website_bindings must be a list")
    bindings[:] = [
        item
        for item in bindings
        if not (
            isinstance(item, Mapping) and item.get("requirement_id") == requirement_id
        )
    ]
    bindings.append(
        {
            "requirement_id": requirement_id,
            "site_id": site_id,
            "page_mapping_sha256": mapping_sha256,
            "control_id": control_id,
            "selector": control["selector"],
            "action_risk": control["action_risk"],
            "raw_label_included": False,
        }
    )
    decisions = original.setdefault("review_decisions", [])
    if not isinstance(decisions, list):
        raise WebsiteBindingError("contract review_decisions must be a list")
    decisions[:] = [
        item
        for item in decisions
        if not (
            isinstance(item, Mapping)
            and item.get("decision_type") == "website_control_binding"
            and item.get("requirement_id") == requirement_id
        )
    ]
    decisions.append(
        {
            "decision_type": "website_control_binding",
            "requirement_id": requirement_id,
            "site_id": site_id,
            "page_mapping_sha256": mapping_sha256,
            "control_id": control_id,
            "human_review_required": True,
        }
    )
    OrganizationContract.from_mapping(original)
    target = Path(output_path).expanduser().resolve()
    write_contract_mapping(
        original,
        target,
        cache_root=cache_root,
        organization_id=contract.organization_id,
        update_output=update_output,
    )
    return WebsiteBindingResult(
        contract_path=target,
        requirement_id=requirement_id,
        site_id=site_id,
        mapping_sha256=mapping_sha256,
        control_id=control_id,
    )
