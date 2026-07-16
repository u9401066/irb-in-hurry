#!/usr/bin/env python3
"""Report KMUH contract provenance and official asset retrieval status."""

from __future__ import annotations

import json

from irb_harness.infrastructure.contract_loader import contract_sha256, load_contract


def main() -> int:
    """Return non-zero until all KMUH source documents and form sets are verified."""
    contract = load_contract(organization_id="kmuh")
    summary = contract.summary()
    summary["contract_sha256"] = contract_sha256(contract)
    summary["ready_for_official_generation"] = not (
        summary["sources_needing_review"]
        or summary["form_sets_needing_retrieval"]
        or summary["workflow_transitions_needing_evidence"]
        or summary["requirements_needing_evidence"]
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["ready_for_official_generation"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
