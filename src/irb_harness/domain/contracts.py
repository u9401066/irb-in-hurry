"""Domain model for an evidence-backed organization IRB contract."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping
from urllib.parse import urlparse


class ContractValidationError(ValueError):
    """Raised when a contract violates a domain invariant."""


class ActionRisk(str, Enum):
    """Risk class used by workflow and browser actions."""

    READ = "read"
    DRAFT_WRITE = "draft_write"
    SUBMIT = "submit"
    DESTRUCTIVE = "destructive"


@dataclass(frozen=True)
class SourceDocument:
    """Identity and provenance of one authoritative source document."""

    source_id: str
    title: str
    uri: str
    media_type: str
    revision: str | None = None
    effective_date: str | None = None
    sha256: str | None = None
    evidence_status: str = "needs_review"

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> SourceDocument:
        return cls(
            source_id=_required_string(value, "source_id"),
            title=_required_string(value, "title"),
            uri=_required_string(value, "uri"),
            media_type=_required_string(value, "media_type"),
            revision=_optional_string(value.get("revision")),
            effective_date=_optional_string(value.get("effective_date")),
            sha256=_optional_sha256(value.get("sha256")),
            evidence_status=str(value.get("evidence_status", "needs_review")),
        )


@dataclass(frozen=True)
class EvidenceReference:
    """A conservative locator from a contract claim to one source document."""

    source_document_id: str
    locator_status: str = "needs_mapping"
    locator_hint: str | None = None
    span_ids: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> EvidenceReference:
        status = str(value.get("locator_status", "needs_mapping"))
        if status not in {"needs_retrieval", "needs_mapping", "verified"}:
            raise ContractValidationError(f"unknown locator_status: {status}")
        span_ids = _string_tuple(value.get("span_ids", []), "evidence span_ids")
        reference = cls(
            source_document_id=_required_string(value, "source_document_id"),
            locator_status=status,
            locator_hint=_optional_string(value.get("locator_hint")),
            span_ids=span_ids,
        )
        if reference.locator_status == "verified" and not reference.span_ids:
            raise ContractValidationError(
                "verified evidence reference must include at least one span_id"
            )
        return reference


@dataclass(frozen=True)
class EvidenceBinding:
    """Hash-verified manifest binding for one contract claim and source."""

    claim_type: str
    claim_id: str
    source_document_id: str
    span_ids: tuple[str, ...]
    span_text_sha256: tuple[tuple[str, str], ...]
    evidence_manifest_sha256: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> EvidenceBinding:
        claim_type, claim_id = _binding_claim_identity(value)
        span_ids = _string_tuple(value.get("span_ids"), "binding span_ids")
        if not span_ids:
            raise ContractValidationError(
                "evidence binding must include at least one span_id"
            )
        raw_hashes = value.get("span_text_sha256")
        if not isinstance(raw_hashes, Mapping):
            raise ContractValidationError(
                "evidence binding span_text_sha256 must be a mapping"
            )
        if set(raw_hashes) != set(span_ids):
            raise ContractValidationError(
                "evidence binding span hashes must match its span_ids"
            )
        hashes = tuple(
            (span_id, _sha256_value(raw_hashes[span_id], "span_text_sha256"))
            for span_id in span_ids
        )
        return cls(
            claim_type=claim_type,
            claim_id=claim_id,
            source_document_id=_required_string(value, "source_document_id"),
            span_ids=span_ids,
            span_text_sha256=hashes,
            evidence_manifest_sha256=_sha256_value(
                value.get("evidence_manifest_sha256"),
                "evidence_manifest_sha256",
            ),
        )

    @property
    def transition_event(self) -> str | None:
        """Backward-compatible semantic alias for workflow bindings."""
        return self.claim_id if self.claim_type == "workflow_transition" else None


@dataclass(frozen=True)
class WorkflowTransition:
    """A state transition in an institution-specific IRB workflow."""

    event: str
    from_states: tuple[str, ...]
    to_state: str
    repeatable: bool = False
    action_risk: ActionRisk = ActionRisk.READ
    human_confirmation: bool = False
    evidence_refs: tuple[EvidenceReference, ...] = ()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> WorkflowTransition:
        raw_states = value.get("from")
        if isinstance(raw_states, str):
            states = (raw_states,)
        elif isinstance(raw_states, list) and all(
            isinstance(item, str) for item in raw_states
        ):
            states = tuple(raw_states)
        else:
            raise ContractValidationError(
                "workflow transition 'from' must be a string or list of strings"
            )
        try:
            risk = ActionRisk(str(value.get("action_risk", ActionRisk.READ.value)))
        except ValueError as exc:
            raise ContractValidationError(
                f"unknown action_risk: {value.get('action_risk')}"
            ) from exc
        transition = cls(
            event=_required_string(value, "event"),
            from_states=states,
            to_state=_required_string(value, "to"),
            repeatable=bool(value.get("repeatable", False)),
            action_risk=risk,
            human_confirmation=bool(value.get("human_confirmation", False)),
            evidence_refs=tuple(
                EvidenceReference.from_mapping(item)
                for item in _nested_mapping_list(value, "evidence_refs")
            ),
        )
        if (
            transition.action_risk in {ActionRisk.SUBMIT, ActionRisk.DESTRUCTIVE}
            and not transition.human_confirmation
        ):
            raise ContractValidationError(
                f"workflow event '{transition.event}' must require human_confirmation"
            )
        return transition


class RequirementKind(str, Enum):
    """Kinds of human-reviewed institutional requirements."""

    DOCUMENT = "document"
    PORTAL_FIELD = "portal_field"
    ELIGIBILITY = "eligibility"
    DEADLINE = "deadline"
    FEE = "fee"
    TRAINING = "training"
    MANUAL_STEP = "manual_step"
    POLICY = "policy"


@dataclass(frozen=True)
class RequirementApplicability:
    """Explicit filters; empty tuples mean the requirement is not filtered there."""

    submission_types: tuple[str, ...] = ()
    review_tracks: tuple[str, ...] = ()
    workflow_events: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RequirementApplicability:
        return cls(
            submission_types=_string_tuple(
                value.get("submission_types", []), "submission_types"
            ),
            review_tracks=_string_tuple(
                value.get("review_tracks", []), "requirement review_tracks"
            ),
            workflow_events=_string_tuple(
                value.get("workflow_events", []), "workflow_events"
            ),
        )

    def matches(
        self,
        *,
        submission_type: str | None = None,
        review_track: str | None = None,
        workflow_event: str | None = None,
    ) -> bool:
        return (
            (
                submission_type is None
                or not self.submission_types
                or submission_type in self.submission_types
            )
            and (
                review_track is None
                or not self.review_tracks
                or review_track in self.review_tracks
            )
            and (
                workflow_event is None
                or not self.workflow_events
                or workflow_event in self.workflow_events
            )
        )


@dataclass(frozen=True)
class ContractRequirement:
    """One evidence-tracked document, portal, or manual institutional requirement."""

    requirement_id: str
    title: str
    kind: RequirementKind
    status: str
    required: bool
    applicability: RequirementApplicability
    value_type: str | None = None
    data_path: str | None = None
    website_site_id: str | None = None
    page_mapping_sha256: str | None = None
    control_id: str | None = None
    evidence_refs: tuple[EvidenceReference, ...] = ()

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> ContractRequirement:
        try:
            kind = RequirementKind(_required_string(value, "kind"))
        except ValueError as exc:
            raise ContractValidationError(
                f"unknown requirement kind: {value.get('kind')}"
            ) from exc
        status = str(value.get("status", "needs_evidence"))
        if status not in {"draft", "needs_evidence", "verified", "deprecated"}:
            raise ContractValidationError(f"unknown requirement status: {status}")
        applicability = value.get("applies_to", {})
        if not isinstance(applicability, Mapping):
            raise ContractValidationError("requirement applies_to must be a mapping")
        value_type = _optional_string(value.get("value_type"))
        if value_type is not None and value_type not in {
            "string",
            "multiline",
            "integer",
            "number",
            "boolean",
            "date",
            "choice",
            "file",
        }:
            raise ContractValidationError(
                f"unknown requirement value_type: {value_type}"
            )
        requirement = cls(
            requirement_id=_required_string(value, "requirement_id"),
            title=_required_string(value, "title"),
            kind=kind,
            status=status,
            required=bool(value.get("required", True)),
            applicability=RequirementApplicability.from_mapping(applicability),
            value_type=value_type,
            data_path=_optional_string(value.get("data_path")),
            website_site_id=_optional_string(value.get("website_site_id")),
            page_mapping_sha256=_optional_sha256(value.get("page_mapping_sha256")),
            control_id=_optional_string(value.get("control_id")),
            evidence_refs=tuple(
                EvidenceReference.from_mapping(item)
                for item in _nested_mapping_list(value, "evidence_refs")
            ),
        )
        if requirement.status == "verified" and (
            not requirement.evidence_refs
            or any(
                reference.locator_status != "verified"
                for reference in requirement.evidence_refs
            )
        ):
            raise ContractValidationError(
                f"verified requirement '{requirement.requirement_id}' needs verified evidence"
            )
        if requirement.data_path and not re.fullmatch(
            r"[A-Za-z_][A-Za-z0-9_.-]*", requirement.data_path
        ):
            raise ContractValidationError(
                f"requirement '{requirement.requirement_id}' has an unsafe data_path"
            )
        mapped_fields = (
            requirement.website_site_id,
            requirement.page_mapping_sha256,
            requirement.control_id,
        )
        if any(mapped_fields) and not all(mapped_fields):
            raise ContractValidationError(
                f"requirement '{requirement.requirement_id}' website mapping must be complete"
            )
        if any(mapped_fields) and requirement.kind is not RequirementKind.PORTAL_FIELD:
            raise ContractValidationError(
                "only portal_field requirements may reference a website control"
            )
        return requirement

    def summary(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "title": self.title,
            "kind": self.kind.value,
            "status": self.status,
            "required": self.required,
            "applies_to": {
                "submission_types": list(self.applicability.submission_types),
                "review_tracks": list(self.applicability.review_tracks),
                "workflow_events": list(self.applicability.workflow_events),
            },
            "value_type": self.value_type,
            "data_path": self.data_path,
            "website_site_id": self.website_site_id,
            "page_mapping_sha256": self.page_mapping_sha256,
            "control_id": self.control_id,
            "evidence_statuses": [
                reference.locator_status for reference in self.evidence_refs
            ],
        }


@dataclass(frozen=True)
class WebsiteControlBinding:
    """A reviewed contract link to one control in a content-addressed page map."""

    requirement_id: str
    site_id: str
    page_mapping_sha256: str
    control_id: str
    selector: str
    action_risk: ActionRisk

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> WebsiteControlBinding:
        try:
            risk = ActionRisk(_required_string(value, "action_risk"))
        except ValueError as exc:
            raise ContractValidationError(
                f"unknown website binding action_risk: {value.get('action_risk')}"
            ) from exc
        if risk in {ActionRisk.SUBMIT, ActionRisk.DESTRUCTIVE}:
            raise ContractValidationError(
                "website binding cannot reference submit or destructive risk"
            )
        if value.get("raw_label_included") is not False:
            raise ContractValidationError(
                "website binding must declare raw_label_included=false"
            )
        return cls(
            requirement_id=_required_string(value, "requirement_id"),
            site_id=_required_string(value, "site_id"),
            page_mapping_sha256=_sha256_value(
                value.get("page_mapping_sha256"), "page_mapping_sha256"
            ),
            control_id=_required_string(value, "control_id"),
            selector=_required_string(value, "selector"),
            action_risk=risk,
        )


@dataclass(frozen=True)
class FormSet:
    """One official submission document bundle and its applicability."""

    form_set_id: str
    title: str
    submission_type: str
    review_tracks: tuple[str, ...]
    source_uri: str
    source_document_id: str
    version: str | None = None
    published_date: str | None = None
    sha256: str | None = None
    evidence_status: str = "needs_retrieval"

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> FormSet:
        tracks = value.get("review_tracks", [])
        if not isinstance(tracks, list) or not all(
            isinstance(item, str) for item in tracks
        ):
            raise ContractValidationError(
                "form_set review_tracks must be a list of strings"
            )
        return cls(
            form_set_id=_required_string(value, "form_set_id"),
            title=_required_string(value, "title"),
            submission_type=_required_string(value, "submission_type"),
            review_tracks=tuple(tracks),
            source_uri=_required_string(value, "source_uri"),
            source_document_id=_required_string(value, "source_document_id"),
            version=_optional_string(value.get("version")),
            published_date=_optional_string(value.get("published_date")),
            sha256=_optional_sha256(value.get("sha256")),
            evidence_status=str(value.get("evidence_status", "needs_retrieval")),
        )


@dataclass(frozen=True)
class WebSiteContract:
    """Browser attachment and safety policy for one institution website."""

    site_id: str
    title: str
    start_url: str
    allowed_hosts: tuple[str, ...]
    login_mode: str
    unauthenticated_selectors: tuple[str, ...] = ()
    authenticated_selectors: tuple[str, ...] = ()
    read_actions: str = "disabled"
    draft_writes: str = "disabled"
    submissions: str = "human_only"

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> WebSiteContract:
        hosts = _string_tuple(value.get("allowed_hosts"), "allowed_hosts")
        start_url = _required_string(value, "start_url")
        parsed = urlparse(start_url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ContractValidationError(
                "website start_url must be an absolute HTTPS URL"
            )
        if parsed.hostname.lower() not in {host.lower() for host in hosts}:
            raise ContractValidationError(
                "website start_url host must be listed in allowed_hosts"
            )
        login = value.get("login", {})
        if not isinstance(login, Mapping):
            raise ContractValidationError("website login must be a mapping")
        policy = value.get("action_policy", {})
        if not isinstance(policy, Mapping):
            raise ContractValidationError("website action_policy must be a mapping")
        return cls(
            site_id=_required_string(value, "site_id"),
            title=_required_string(value, "title"),
            start_url=start_url,
            allowed_hosts=hosts,
            login_mode=str(login.get("mode", "human")),
            unauthenticated_selectors=_string_tuple(
                login.get("unauthenticated_selectors", []),
                "unauthenticated_selectors",
            ),
            authenticated_selectors=_string_tuple(
                login.get("authenticated_selectors", []),
                "authenticated_selectors",
            ),
            read_actions=str(policy.get("read_actions", "disabled")),
            draft_writes=str(policy.get("draft_writes", "disabled")),
            submissions=str(policy.get("submissions", "human_only")),
        )


@dataclass(frozen=True)
class OrganizationContract:
    """Validated organization contract compiled from authoritative documents."""

    schema_version: str
    contract_id: str
    status: str
    organization_id: str
    organization_name: str
    default_locale: str
    source_documents: tuple[SourceDocument, ...] = field(default_factory=tuple)
    workflow_states: tuple[str, ...] = field(default_factory=tuple)
    workflow_transitions: tuple[WorkflowTransition, ...] = field(default_factory=tuple)
    requirements: tuple[ContractRequirement, ...] = field(default_factory=tuple)
    evidence_bindings: tuple[EvidenceBinding, ...] = field(default_factory=tuple)
    website_bindings: tuple[WebsiteControlBinding, ...] = field(default_factory=tuple)
    form_sets: tuple[FormSet, ...] = field(default_factory=tuple)
    websites: tuple[WebSiteContract, ...] = field(default_factory=tuple)
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> OrganizationContract:
        organization = value.get("organization")
        if not isinstance(organization, Mapping):
            raise ContractValidationError("organization must be a mapping")
        workflow = value.get("workflow", {})
        if not isinstance(workflow, Mapping):
            raise ContractValidationError("workflow must be a mapping")
        sources = tuple(
            SourceDocument.from_mapping(item)
            for item in _mapping_list(value, "source_documents")
        )
        transitions = tuple(
            WorkflowTransition.from_mapping(item)
            for item in _mapping_list(workflow, "transitions")
        )
        form_sets = tuple(
            FormSet.from_mapping(item) for item in _mapping_list(value, "form_sets")
        )
        requirements = tuple(
            ContractRequirement.from_mapping(item)
            for item in _mapping_list(value, "requirements")
        )
        evidence_bindings = tuple(
            EvidenceBinding.from_mapping(item)
            for item in _mapping_list(value, "evidence_bindings")
        )
        website_bindings = tuple(
            WebsiteControlBinding.from_mapping(item)
            for item in _mapping_list(value, "website_bindings")
        )
        websites = tuple(
            WebSiteContract.from_mapping(item)
            for item in _mapping_list(value, "websites")
        )
        states = _string_tuple(workflow.get("states", []), "workflow states")
        contract = cls(
            schema_version=_required_string(value, "schema_version"),
            contract_id=_required_string(value, "contract_id"),
            status=str(value.get("status", "draft")),
            organization_id=_required_string(organization, "id"),
            organization_name=_required_string(organization, "name"),
            default_locale=str(organization.get("default_locale", "zh-TW")),
            source_documents=sources,
            workflow_states=states,
            workflow_transitions=transitions,
            requirements=requirements,
            evidence_bindings=evidence_bindings,
            website_bindings=website_bindings,
            form_sets=form_sets,
            websites=websites,
            raw=dict(value),
        )
        contract.validate()
        return contract

    def validate(self) -> None:
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", self.organization_id):
            raise ContractValidationError(
                "organization id must be a lowercase filesystem-safe identifier"
            )
        _ensure_unique(
            (item.source_id for item in self.source_documents), "source_document"
        )
        _ensure_unique((item.form_set_id for item in self.form_sets), "form_set")
        _ensure_unique(
            (item.requirement_id for item in self.requirements), "requirement"
        )
        _ensure_unique((item.site_id for item in self.websites), "website")
        for website in self.websites:
            if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", website.site_id):
                raise ContractValidationError(
                    "website site_id must be a lowercase filesystem-safe identifier"
                )
        _ensure_unique(
            (transition.event for transition in self.workflow_transitions),
            "workflow event",
        )
        state_set = set(self.workflow_states)
        for transition in self.workflow_transitions:
            unknown = (set(transition.from_states) | {transition.to_state}) - state_set
            if unknown:
                raise ContractValidationError(
                    f"workflow event '{transition.event}' references unknown states: {sorted(unknown)}"
                )
        source_ids = {item.source_id for item in self.source_documents}
        source_by_id = {item.source_id: item for item in self.source_documents}
        transitions_by_event = {
            transition.event: transition for transition in self.workflow_transitions
        }
        requirements_by_id = {
            requirement.requirement_id: requirement for requirement in self.requirements
        }
        website_ids = {website.site_id for website in self.websites}
        for requirement in self.requirements:
            if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", requirement.requirement_id):
                raise ContractValidationError(
                    "requirement_id must be a lowercase filesystem-safe identifier"
                )
            unknown_events = set(requirement.applicability.workflow_events) - set(
                transitions_by_event
            )
            if unknown_events:
                raise ContractValidationError(
                    f"requirement '{requirement.requirement_id}' references unknown "
                    f"workflow events: {sorted(unknown_events)}"
                )
            if (
                requirement.website_site_id is not None
                and requirement.website_site_id not in website_ids
            ):
                raise ContractValidationError(
                    f"requirement '{requirement.requirement_id}' references unknown "
                    f"website '{requirement.website_site_id}'"
                )
        website_binding_by_requirement: dict[str, WebsiteControlBinding] = {}
        for website_binding in self.website_bindings:
            if website_binding.requirement_id in website_binding_by_requirement:
                raise ContractValidationError(
                    f"duplicate website binding for requirement "
                    f"'{website_binding.requirement_id}'"
                )
            website_binding_by_requirement[website_binding.requirement_id] = (
                website_binding
            )
            bound_requirement = requirements_by_id.get(website_binding.requirement_id)
            if bound_requirement is None:
                raise ContractValidationError(
                    f"website binding references unknown requirement "
                    f"'{website_binding.requirement_id}'"
                )
            if bound_requirement.kind is not RequirementKind.PORTAL_FIELD:
                raise ContractValidationError(
                    "website binding requires a portal_field requirement"
                )
            if website_binding.site_id not in website_ids:
                raise ContractValidationError(
                    f"website binding references unknown website "
                    f"'{website_binding.site_id}'"
                )
            if (
                bound_requirement.website_site_id != website_binding.site_id
                or bound_requirement.page_mapping_sha256
                != website_binding.page_mapping_sha256
                or bound_requirement.control_id != website_binding.control_id
            ):
                raise ContractValidationError(
                    f"website binding does not match requirement "
                    f"'{bound_requirement.requirement_id}'"
                )
        for requirement in self.requirements:
            if (
                requirement.website_site_id is not None
                and requirement.requirement_id not in website_binding_by_requirement
            ):
                raise ContractValidationError(
                    f"mapped portal requirement '{requirement.requirement_id}' "
                    "requires a website binding"
                )
        binding_keys: set[tuple[str, str, str]] = set()
        for binding in self.evidence_bindings:
            key = (binding.claim_type, binding.claim_id, binding.source_document_id)
            if key in binding_keys:
                raise ContractValidationError(
                    f"duplicate evidence binding: {binding.claim_type}/"
                    f"{binding.claim_id}/"
                    f"{binding.source_document_id}"
                )
            binding_keys.add(key)
            if (
                binding.claim_type == "workflow_transition"
                and binding.claim_id not in transitions_by_event
            ):
                raise ContractValidationError(
                    "evidence binding references unknown workflow event "
                    f"'{binding.claim_id}'"
                )
            if (
                binding.claim_type == "requirement"
                and binding.claim_id not in requirements_by_id
            ):
                raise ContractValidationError(
                    "evidence binding references unknown requirement "
                    f"'{binding.claim_id}'"
                )
            if binding.source_document_id not in source_ids:
                raise ContractValidationError(
                    "evidence binding references unknown source_document_id "
                    f"'{binding.source_document_id}'"
                )
        claims: list[tuple[str, str, tuple[EvidenceReference, ...]]] = [
            ("workflow_transition", transition.event, transition.evidence_refs)
            for transition in self.workflow_transitions
        ]
        claims.extend(
            ("requirement", requirement.requirement_id, requirement.evidence_refs)
            for requirement in self.requirements
        )
        for claim_type, claim_id, references in claims:
            for reference in references:
                if reference.source_document_id not in source_ids:
                    raise ContractValidationError(
                        f"{claim_type} '{claim_id}' references unknown source_document_id "
                        f"'{reference.source_document_id}'"
                    )
                if (
                    reference.locator_status == "verified"
                    and not source_by_id[reference.source_document_id].sha256
                ):
                    raise ContractValidationError(
                        f"{claim_type} '{claim_id}' cannot verify evidence against "
                        f"an unhashed source '{reference.source_document_id}'"
                    )
                if reference.locator_status == "verified":
                    matching_binding = next(
                        (
                            item
                            for item in self.evidence_bindings
                            if item.claim_type == claim_type
                            and item.claim_id == claim_id
                            and item.source_document_id == reference.source_document_id
                        ),
                        None,
                    )
                    if (
                        matching_binding is None
                        or matching_binding.span_ids != reference.span_ids
                    ):
                        raise ContractValidationError(
                            f"verified evidence for {claim_type} '{claim_id}' "
                            "requires a matching evidence binding"
                        )
        for binding in self.evidence_bindings:
            if binding.claim_type == "workflow_transition":
                references = transitions_by_event[binding.claim_id].evidence_refs
            else:
                references = requirements_by_id[binding.claim_id].evidence_refs
            if not any(
                reference.source_document_id == binding.source_document_id
                and reference.locator_status == "verified"
                and reference.span_ids == binding.span_ids
                for reference in references
            ):
                raise ContractValidationError(
                    f"evidence binding for {binding.claim_type} '{binding.claim_id}' "
                    "does not match a verified evidence reference"
                )
        for form_set in self.form_sets:
            if form_set.source_document_id not in source_ids:
                raise ContractValidationError(
                    f"form_set '{form_set.form_set_id}' references unknown source_document_id "
                    f"'{form_set.source_document_id}'"
                )

    def website(self, site_id: str) -> WebSiteContract:
        for website in self.websites:
            if website.site_id == site_id:
                return website
        raise ContractValidationError(f"unknown website: {site_id}")

    def requirements_for(
        self,
        *,
        submission_type: str | None = None,
        review_track: str | None = None,
        workflow_event: str | None = None,
    ) -> tuple[ContractRequirement, ...]:
        """Select non-deprecated requirements without evaluating hidden rule logic."""
        return tuple(
            requirement
            for requirement in self.requirements
            if requirement.status != "deprecated"
            and requirement.applicability.matches(
                submission_type=submission_type,
                review_track=review_track,
                workflow_event=workflow_event,
            )
        )

    def summary(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "contract_id": self.contract_id,
            "status": self.status,
            "organization": {
                "id": self.organization_id,
                "name": self.organization_name,
                "default_locale": self.default_locale,
            },
            "source_document_count": len(self.source_documents),
            "form_set_count": len(self.form_sets),
            "requirement_count": len(self.requirements),
            "workflow_state_count": len(self.workflow_states),
            "workflow_transition_count": len(self.workflow_transitions),
            "verified_evidence_binding_count": len(self.evidence_bindings),
            "website_ids": [website.site_id for website in self.websites],
            "sources_needing_review": [
                source.source_id
                for source in self.source_documents
                if source.evidence_status != "verified" or not source.sha256
            ],
            "form_sets_needing_retrieval": [
                form_set.form_set_id
                for form_set in self.form_sets
                if form_set.evidence_status != "verified" or not form_set.sha256
            ],
            "workflow_transitions_needing_evidence": [
                transition.event
                for transition in self.workflow_transitions
                if not transition.evidence_refs
                or any(
                    reference.locator_status != "verified"
                    for reference in transition.evidence_refs
                )
            ],
            "requirements_needing_evidence": [
                requirement.requirement_id
                for requirement in self.requirements
                if requirement.status != "verified"
                or not requirement.evidence_refs
                or any(
                    reference.locator_status != "verified"
                    for reference in requirement.evidence_refs
                )
            ],
        }


def _required_string(value: Mapping[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result.strip():
        raise ContractValidationError(f"{key} must be a non-empty string")
    return result.strip()


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ContractValidationError("optional string field must be a string or null")
    return value


def _sha256_value(value: Any, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ContractValidationError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _optional_sha256(value: Any) -> str | None:
    if value is None:
        return None
    return _sha256_value(value, "sha256")


def _binding_claim_identity(value: Mapping[str, Any]) -> tuple[str, str]:
    claim_type = value.get("claim_type")
    claim_id = value.get("claim_id")
    if claim_type is None and claim_id is None:
        if value.get("transition_event") is not None:
            return "workflow_transition", _required_string(value, "transition_event")
        if value.get("requirement_id") is not None:
            return "requirement", _required_string(value, "requirement_id")
    if claim_type not in {"workflow_transition", "requirement"}:
        raise ContractValidationError(
            f"unknown evidence binding claim_type: {claim_type}"
        )
    return str(claim_type), _required_string(value, "claim_id")


def _mapping_list(value: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    raw = value.get(key, [])
    if not isinstance(raw, list) or not all(isinstance(item, Mapping) for item in raw):
        raise ContractValidationError(f"{key} must be a list of mappings")
    return raw


def _nested_mapping_list(value: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    raw = value.get(key, [])
    if not isinstance(raw, list) or not all(isinstance(item, Mapping) for item in raw):
        raise ContractValidationError(f"{key} must be a list of mappings")
    return raw


def _string_tuple(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise ContractValidationError(f"{label} must be a list of non-empty strings")
    return tuple(value)


def _ensure_unique(values: Any, label: str) -> None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise ContractValidationError(f"duplicate {label} id: {value}")
        seen.add(value)
