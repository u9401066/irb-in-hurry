# IRB-in-Hurry

> Architecture migration in progress: the new `irb_harness` core turns
> organization-provided documents into evidence-tracked contracts, with KMUH as
> the bundled default. The historical `scripts/generators` modules remain a
> KFSYSCC compatibility layer and are not official KMUH forms.

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/u9401066/irb-in-hurry/actions/workflows/ci.yml/badge.svg)](https://github.com/u9401066/irb-in-hurry/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-72%20passed-brightgreen.svg)](#validation)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-087f8c.svg)](https://u9401066.github.io/irb-in-hurry/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

IRB-in-Hurry is a citation-ready document and browser harness for institutional
review board workflows. It does not bypass ethics review, approve studies, or
submit applications. It reduces repetitive work while keeping institutional
rules traceable to the exact source bytes and text spans reviewed by a human.

[繁體中文版 README](README.zh-TW.md) ·
[Documentation site](https://u9401066.github.io/irb-in-hurry/)

## What changed in this fork

The original project encoded KFSYSCC form IDs and routing rules directly in
generators. That works only for that institution. This fork introduces an
organization contract with five separate concerns:

1. Immutable organization-provided source documents.
2. Human-reviewed workflow, requirement, and form applicability rules.
3. Evidence bindings with source, manifest, span, and text hashes.
4. Document adapters that consume reviewed contracts.
5. Browser adapters that attach only after a human signs in.

Contract compilation never infers institutional policy. A successful download
is still marked `retrieved_needs_rule_mapping`; only a reviewed evidence mapping
can become `verified`.

## KMUH default

The bundled contract currently declares:

- 11 official source records;
- 8 form sets;
- 16 event-based workflow transitions;
- 9 conservative candidate requirements;
- the public KMUH clinical-trial directory and human-login eIRB portal.

The candidate requirements remain `needs_evidence` until the official source
bytes are retrieved and their locators are reviewed. They must not be treated as
verified KMUH policy yet.

KMUH is modeled as an event graph, not a fixed new → amendment → continuing →
closure sequence. Revision, safety reporting, non-compliance, suspension,
termination, closure, and withdrawal are independent branches where applicable.

## Quick start

```bash
uv sync --group dev

# Validate the bundled KMUH contract and show outstanding evidence work.
uv run irb-contract show

# Query explicit applicability dimensions without hidden rule inference.
uv run irb-contract requirements \
  --submission-type new \
  --review-track general \
  --workflow-event submit_new
```

Compile another institution's PDF, DOCX, Markdown, HTML, or text documents into
a draft contract and evidence index:

```bash
uv run irb-contract compile \
  --institution example \
  --name "Example IRB" \
  --document /path/to/instructions.pdf \
  --document /path/to/forms.docx \
  --output output/contracts/example.yml
```

The compiler records byte and text SHA-256 values, content-stable source/span
IDs, line/character/UTF-8 byte offsets, and short context. Repeated identical inputs are
deduplicated, outputs are deterministic, and neither the contract nor evidence
index contains a workstation absolute path. A reviewer then uses `map-workflow`
to create or replace an explicit transition, `map-evidence` to bind an existing
transition, or `map-requirement` to upsert a requirement from selected spans.

When the execution host cannot reach an institution's official URL, a human may
download that declared asset in a browser and copy it into the workspace:

```bash
uv run irb-contract import-local \
  --source kmuh_sop_02_01 \
  --file /path/to/official/KMUH-SOP-02-01.pdf \
  --human-confirmed-source
```

Online retrieval and local import both verify the declared asset selection and
file signature/container, so an HTML error page cannot masquerade as a PDF,
DOCX, or ZIP. The importer also verifies stable bytes and the immutable cache
copy. It records a local-copy acquisition mode
without storing the original absolute path. Existing SHA-256 changes require
explicit `--allow-revision`; import still stops at `needs_mapping`.

See [README.zh-TW.md](README.zh-TW.md) for the complete synchronization and
mapping commands, and [contract architecture](docs/contract-architecture.md)
for the invariants.

## Human-login KMUH Browser MCP

The browser server receives no KMUH credentials. It attaches over Chrome DevTools
Protocol to a dedicated Chromium profile after a human signs in.

```bash
uv run irb-contract browser-status
uv run irb-contract list-pages
uv run irb-contract session-status --site kmuh_eirb
uv run irb-contract map-page --site kmuh_eirb
uv run irb-web-mcp
```

Page mappings keep selectors, hashed identities, and action risk, but exclude
field values, body text, case links, and raw labels. There are no submit,
approval, withdrawal, termination, or delete MCP tools. Draft writes and reviewed
read clicks each require separate runtime switches and exact human confirmation.
Draft fields must also resolve through one reviewed portal requirement, mapping
digest, and control binding; arbitrary selector writes fail closed.

Remote SSH users must reverse-forward the desktop Chrome loopback port to the
execution host. See the [KMUH Browser MCP guide](docs/kmuh-browser-mcp.md).

## Legacy KFSYSCC compatibility

The existing DOCX generators, PDF/PNG conversion, checklist, and dashboard
remain available for KFSYSCC configurations:

```bash
cp tests/fixtures/sample_retrospective.yml config.yml
make all
```

If `institution: kmuh` is selected, the legacy generator path fails closed
instead of relabeling KFSYSCC SF forms as KMUH forms.

## Validation

```bash
uv run ruff check src/irb_harness scripts/report_kmuh.py tests/
uv run mypy src --ignore-missing-imports
uv run pytest tests/ -q
uv build
git diff --check
```

The 72 regression tests cover deterministic path-free contract compilation,
contract and evidence validation, signature-checked online and offline source
acquisition, requirement mapping, reviewed portal writes, browser safety policy,
the GitHub Pages site, and the retained KFSYSCC generation path.

## Project map

```text
src/irb_harness/
├── domain/          # pure contracts and safety invariants
├── application/     # compile, sync, evidence, requirement and website mapping
├── infrastructure/  # document, archive, browser and policy adapters
├── presentation/    # CLI and MCP tools
└── contracts/       # bundled organization contracts (KMUH default)

docs/                # architecture and operator guides
site/                # dependency-free GitHub Pages site
scripts/generators/  # historical KFSYSCC compatibility layer
```

## License

[MIT](LICENSE)
