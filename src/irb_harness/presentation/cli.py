"""Command line interface for contracts and browser discovery."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Sequence

import yaml

from irb_harness.application.contract_compiler import compile_contract_from_documents
from irb_harness.application.evidence_mapping import map_workflow_evidence
from irb_harness.application.page_mapping import (
    sanitize_page_discovery,
    write_page_mapping,
)
from irb_harness.application.requirement_mapping import map_requirement_from_evidence
from irb_harness.application.source_sync import (
    import_contract_asset,
    sync_contract_sources,
)
from irb_harness.application.website_binding import bind_requirement_to_control
from irb_harness.application.workflow_mapping import map_workflow_from_evidence
from irb_harness.infrastructure.browser_session import BrowserController
from irb_harness.infrastructure.contract_loader import (
    contract_sha256,
    load_contract,
    load_contract_mapping,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="irb-contract")
    subcommands = parser.add_subparsers(dest="command", required=True)

    show = subcommands.add_parser(
        "show", help="validate and summarize an organization contract"
    )
    show.add_argument("--contract")
    show.add_argument("--organization", default="kmuh")

    requirements = subcommands.add_parser(
        "requirements",
        help="list applicable contract requirements with evidence readiness",
    )
    requirements.add_argument("--contract")
    requirements.add_argument("--organization", default="kmuh")
    requirements.add_argument("--submission-type")
    requirements.add_argument("--review-track")
    requirements.add_argument("--workflow-event")

    compile_parser = subcommands.add_parser(
        "compile",
        help="ingest organization documents into a citation-ready contract draft",
    )
    compile_parser.add_argument("--institution", required=True)
    compile_parser.add_argument("--name", required=True)
    compile_parser.add_argument("--document", action="append", required=True)
    compile_parser.add_argument("--output", required=True)
    compile_parser.add_argument("--base-contract")
    compile_parser.add_argument("--force", action="store_true")

    sync_sources = subcommands.add_parser(
        "sync-sources",
        help="retrieve contract-declared assets into an immutable evidence cache",
    )
    sync_sources.add_argument("--contract")
    sync_sources.add_argument("--organization", default="kmuh")
    sync_sources.add_argument("--source", action="append", default=[])
    sync_sources.add_argument("--form-set", action="append", default=[])
    sync_sources.add_argument("--cache", default=".irb-source-cache")
    sync_sources.add_argument("--output")
    sync_sources.add_argument("--continue-on-error", action="store_true")
    sync_sources.add_argument("--update-output", action="store_true")
    sync_sources.add_argument("--allow-revision", action="store_true")

    import_local = subcommands.add_parser(
        "import-local",
        help="import one human-confirmed declared asset from a local file",
    )
    import_local.add_argument("--contract")
    import_local.add_argument("--organization", default="kmuh")
    selected_asset = import_local.add_mutually_exclusive_group(required=True)
    selected_asset.add_argument("--source")
    selected_asset.add_argument("--form-set")
    import_local.add_argument("--file", required=True)
    import_local.add_argument("--cache", default=".irb-source-cache")
    import_local.add_argument("--output")
    import_local.add_argument(
        "--human-confirmed-source", action="store_true", required=True
    )
    import_local.add_argument("--allow-revision", action="store_true")
    import_local.add_argument("--update-output", action="store_true")

    map_evidence = subcommands.add_parser(
        "map-evidence",
        help="bind a human-reviewed workflow claim to verified evidence spans",
    )
    map_evidence.add_argument("--contract")
    map_evidence.add_argument("--organization", default="kmuh")
    map_evidence.add_argument("--manifest", required=True)
    map_evidence.add_argument("--transition", required=True)
    map_evidence.add_argument("--source", required=True)
    map_evidence.add_argument("--span", action="append", required=True)
    map_evidence.add_argument("--cache", default=".irb-source-cache")
    map_evidence.add_argument("--output")
    map_evidence.add_argument("--update-output", action="store_true")

    map_workflow = subcommands.add_parser(
        "map-workflow",
        help="add or replace a reviewed workflow transition using verified evidence",
    )
    map_workflow.add_argument("--contract")
    map_workflow.add_argument("--organization", default="kmuh")
    map_workflow.add_argument("--definition", required=True)
    map_workflow.add_argument("--manifest", required=True)
    map_workflow.add_argument("--source", required=True)
    map_workflow.add_argument("--span", action="append", required=True)
    map_workflow.add_argument("--locator-hint")
    map_workflow.add_argument("--cache", default=".irb-source-cache")
    map_workflow.add_argument("--output")
    map_workflow.add_argument("--replace-transition", action="store_true")
    map_workflow.add_argument("--update-output", action="store_true")

    map_requirement = subcommands.add_parser(
        "map-requirement",
        help="add or replace a reviewed requirement using verified evidence spans",
    )
    map_requirement.add_argument("--contract")
    map_requirement.add_argument("--organization", default="kmuh")
    map_requirement.add_argument("--definition", required=True)
    map_requirement.add_argument("--manifest", required=True)
    map_requirement.add_argument("--source", required=True)
    map_requirement.add_argument("--span", action="append", required=True)
    map_requirement.add_argument("--locator-hint")
    map_requirement.add_argument("--cache", default=".irb-source-cache")
    map_requirement.add_argument("--output")
    map_requirement.add_argument("--replace-requirement", action="store_true")
    map_requirement.add_argument("--update-output", action="store_true")

    browser_status = subcommands.add_parser(
        "browser-status", help="probe the human-login CDP bridge"
    )
    browser_status.add_argument("--endpoint")

    list_pages = subcommands.add_parser(
        "list-pages", help="list open pages without titles or form values"
    )
    list_pages.add_argument("--endpoint")

    session_status = subcommands.add_parser(
        "session-status", help="check whether an open institution page is authenticated"
    )
    session_status.add_argument("--contract")
    session_status.add_argument("--organization", default="kmuh")
    session_status.add_argument("--site", required=True)
    session_status.add_argument("--endpoint")
    session_status.add_argument("--page-ref")

    discover = subcommands.add_parser(
        "discover", help="inventory controls on an open authenticated page"
    )
    discover.add_argument("--contract")
    discover.add_argument("--organization", default="kmuh")
    discover.add_argument("--site", required=True)
    discover.add_argument("--endpoint")
    discover.add_argument("--page-ref")

    map_page = subcommands.add_parser(
        "map-page", help="write a value-free mapping for an open authenticated page"
    )
    map_page.add_argument("--contract")
    map_page.add_argument("--organization", default="kmuh")
    map_page.add_argument("--site", required=True)
    map_page.add_argument("--endpoint")
    map_page.add_argument("--page-ref")
    map_page.add_argument("--output")
    map_page.add_argument("--force", action="store_true")

    bind_control = subcommands.add_parser(
        "bind-requirement-control",
        help="bind a portal_field requirement to a reviewed page-map control",
    )
    bind_control.add_argument("--contract")
    bind_control.add_argument("--organization", default="kmuh")
    bind_control.add_argument("--requirement", required=True)
    bind_control.add_argument("--site", required=True)
    bind_control.add_argument("--mapping-sha256", required=True)
    bind_control.add_argument("--control-id", required=True)
    bind_control.add_argument("--mapping-root", default=".irb-web-artifacts")
    bind_control.add_argument("--cache", default=".irb-source-cache")
    bind_control.add_argument("--output")
    bind_control.add_argument("--replace-binding", action="store_true")
    bind_control.add_argument("--update-output", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "show":
        contract = load_contract(args.contract, organization_id=args.organization)
        result = contract.summary()
        result["contract_sha256"] = contract_sha256(contract)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "requirements":
        contract = load_contract(args.contract, organization_id=args.organization)
        selected = contract.requirements_for(
            submission_type=args.submission_type,
            review_track=args.review_track,
            workflow_event=args.workflow_event,
        )
        print(
            json.dumps(
                {
                    "contract_id": contract.contract_id,
                    "count": len(selected),
                    "requirements": [item.summary() for item in selected],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.command == "compile":
        base = load_contract_mapping(args.base_contract) if args.base_contract else None
        contract_path, evidence_path = compile_contract_from_documents(
            args.institution,
            args.name,
            [Path(item) for item in args.document],
            args.output,
            base_contract=base,
            force=args.force,
        )
        print(
            json.dumps(
                {"contract": str(contract_path), "evidence": str(evidence_path)},
                ensure_ascii=False,
            )
        )
        return 0
    if args.command == "sync-sources":
        mapping = load_contract_mapping(
            args.contract, organization_id=args.organization
        )
        output = args.output or f"organizations/{args.organization}/contract.yml"
        sync_result = sync_contract_sources(
            mapping,
            output_path=output,
            cache_root=args.cache,
            source_ids=args.source,
            form_set_ids=args.form_set,
            continue_on_error=args.continue_on_error,
            update_output=args.update_output,
            allow_revision=args.allow_revision,
        )
        print(
            json.dumps(
                {
                    "contract": str(sync_result.contract_path),
                    "manifest": str(sync_result.manifest_path),
                    "retrieved_ids": sync_result.retrieved_ids,
                    "failed_ids": sync_result.failed_ids,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.command == "import-local":
        mapping = load_contract_mapping(
            args.contract, organization_id=args.organization
        )
        output = args.output or f"organizations/{args.organization}/contract.yml"
        import_result = import_contract_asset(
            mapping,
            local_file=args.file,
            output_path=output,
            cache_root=args.cache,
            source_id=args.source,
            form_set_id=args.form_set,
            human_source_identity_confirmed=args.human_confirmed_source,
            update_output=args.update_output,
            allow_revision=args.allow_revision,
        )
        print(
            json.dumps(
                {
                    "contract": str(import_result.contract_path),
                    "manifest": str(import_result.manifest_path),
                    "imported_ids": import_result.retrieved_ids,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.command == "map-evidence":
        mapping = load_contract_mapping(
            args.contract, organization_id=args.organization
        )
        output = args.output or f"organizations/{args.organization}/contract.yml"
        evidence_result = map_workflow_evidence(
            mapping,
            evidence_manifest_path=args.manifest,
            transition_event=args.transition,
            source_document_id=args.source,
            span_ids=args.span,
            output_path=output,
            cache_root=args.cache,
            update_output=args.update_output,
        )
        print(
            json.dumps(
                {
                    "contract": str(evidence_result.contract_path),
                    "transition": evidence_result.transition_event,
                    "source": evidence_result.source_document_id,
                    "span_ids": evidence_result.span_ids,
                    "evidence_manifest_sha256": (
                        evidence_result.evidence_manifest_sha256
                    ),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.command == "map-workflow":
        mapping = load_contract_mapping(
            args.contract, organization_id=args.organization
        )
        definition_path = Path(args.definition).expanduser().resolve()
        definition = yaml.safe_load(definition_path.read_text(encoding="utf-8"))
        if not isinstance(definition, dict):
            raise ValueError("workflow definition root must be a mapping")
        output = args.output or f"organizations/{args.organization}/contract.yml"
        workflow_result = map_workflow_from_evidence(
            mapping,
            transition_definition=definition,
            evidence_manifest_path=args.manifest,
            source_document_id=args.source,
            span_ids=args.span,
            output_path=output,
            locator_hint=args.locator_hint,
            cache_root=args.cache,
            replace_transition=args.replace_transition,
            update_output=args.update_output,
        )
        print(
            json.dumps(
                {
                    "contract": str(workflow_result.contract_path),
                    "transition": workflow_result.transition_event,
                    "source": workflow_result.source_document_id,
                    "span_ids": workflow_result.span_ids,
                    "states_added": workflow_result.states_added,
                    "definition_sha256": workflow_result.definition_sha256,
                    "evidence_manifest_sha256": (
                        workflow_result.evidence_manifest_sha256
                    ),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.command == "map-requirement":
        mapping = load_contract_mapping(
            args.contract, organization_id=args.organization
        )
        definition_path = Path(args.definition).expanduser().resolve()
        definition = yaml.safe_load(definition_path.read_text(encoding="utf-8"))
        if not isinstance(definition, dict):
            raise ValueError("requirement definition root must be a mapping")
        output = args.output or f"organizations/{args.organization}/contract.yml"
        requirement_result = map_requirement_from_evidence(
            mapping,
            requirement_definition=definition,
            evidence_manifest_path=args.manifest,
            source_document_id=args.source,
            span_ids=args.span,
            output_path=output,
            locator_hint=args.locator_hint,
            cache_root=args.cache,
            replace_requirement=args.replace_requirement,
            update_output=args.update_output,
        )
        print(
            json.dumps(
                {
                    "contract": str(requirement_result.contract_path),
                    "requirement_id": requirement_result.requirement_id,
                    "status": requirement_result.requirement_status,
                    "source": requirement_result.source_document_id,
                    "span_ids": requirement_result.span_ids,
                    "definition_sha256": requirement_result.definition_sha256,
                    "evidence_manifest_sha256": (
                        requirement_result.evidence_manifest_sha256
                    ),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.command == "browser-status":
        print(
            json.dumps(
                BrowserController(args.endpoint).endpoint_status(),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.command == "list-pages":
        print(
            json.dumps(
                asyncio.run(BrowserController(args.endpoint).list_pages()),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.command == "session-status":
        contract = load_contract(args.contract, organization_id=args.organization)
        result = asyncio.run(
            BrowserController(args.endpoint).session_status(
                contract.website(args.site), page_ref=args.page_ref
            )
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "discover":
        contract = load_contract(args.contract, organization_id=args.organization)
        website = contract.website(args.site)
        result = asyncio.run(
            BrowserController(args.endpoint).discover_current_page(
                website, page_ref=args.page_ref
            )
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "map-page":
        contract = load_contract(args.contract, organization_id=args.organization)
        website = contract.website(args.site)
        discovery = asyncio.run(
            BrowserController(args.endpoint).discover_current_page(
                website, page_ref=args.page_ref
            )
        )
        preview = sanitize_page_discovery(discovery)
        output = args.output or (
            f".irb-web-artifacts/{args.organization}/{args.site}/"
            f"{preview['mapping_sha256']}.json"
        )
        target, mapping = write_page_mapping(discovery, output, force=args.force)
        print(
            json.dumps(
                {
                    "mapping": str(target),
                    "mapping_sha256": mapping["mapping_sha256"],
                    "control_count": mapping["control_count"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if args.command == "bind-requirement-control":
        mapping = load_contract_mapping(
            args.contract, organization_id=args.organization
        )
        output = args.output or f"organizations/{args.organization}/contract.yml"
        binding_result = bind_requirement_to_control(
            mapping,
            requirement_id=args.requirement,
            site_id=args.site,
            mapping_sha256=args.mapping_sha256,
            control_id=args.control_id,
            output_path=output,
            mapping_root=args.mapping_root,
            cache_root=args.cache,
            replace_binding=args.replace_binding,
            update_output=args.update_output,
        )
        print(
            json.dumps(
                {
                    "contract": str(binding_result.contract_path),
                    "requirement_id": binding_result.requirement_id,
                    "site_id": binding_result.site_id,
                    "mapping_sha256": binding_result.mapping_sha256,
                    "control_id": binding_result.control_id,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
