"""Load organization contracts from explicit, workspace, or bundled locations."""

from __future__ import annotations

import hashlib
import json
import os
from importlib.resources import as_file, files
from pathlib import Path
from typing import Any, Mapping

import yaml

from irb_harness.domain.contracts import ContractValidationError, OrganizationContract


DEFAULT_ORGANIZATION = "kmuh"


def resolve_contract_path(
    path: str | Path | None = None,
    *,
    organization_id: str = DEFAULT_ORGANIZATION,
) -> Path:
    """Resolve a contract without silently accepting an unknown organization."""
    if path is not None:
        resolved = Path(path).expanduser().resolve()
        if not resolved.is_file():
            raise FileNotFoundError(f"contract not found: {resolved}")
        return resolved

    configured = os.environ.get("IRB_ORGANIZATION_CONTRACT")
    if configured:
        return resolve_contract_path(configured, organization_id=organization_id)

    workspace_candidate = (
        Path.cwd() / "organizations" / organization_id / "contract.yml"
    )
    if workspace_candidate.is_file():
        return workspace_candidate.resolve()

    resource = files("irb_harness.contracts").joinpath(f"{organization_id}.yml")
    if not resource.is_file():
        raise FileNotFoundError(f"unknown organization contract: {organization_id}")
    with as_file(resource) as resource_path:
        return Path(resource_path)


def load_contract_mapping(
    path: str | Path | None = None,
    *,
    organization_id: str = DEFAULT_ORGANIZATION,
) -> dict[str, Any]:
    resolved = resolve_contract_path(path, organization_id=organization_id)
    with resolved.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if not isinstance(loaded, Mapping):
        raise ContractValidationError("contract root must be a mapping")
    return dict(loaded)


def load_contract(
    path: str | Path | None = None,
    *,
    organization_id: str = DEFAULT_ORGANIZATION,
) -> OrganizationContract:
    return OrganizationContract.from_mapping(
        load_contract_mapping(path, organization_id=organization_id)
    )


def contract_sha256(contract: OrganizationContract | Mapping[str, Any]) -> str:
    value = contract.raw if isinstance(contract, OrganizationContract) else contract
    canonical = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
