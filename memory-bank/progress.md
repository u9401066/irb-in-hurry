# Progress

Last updated: 2026-07-16

## Done

- [x] Define and validate organization, source, workflow, form, requirement, and
  website contracts.
- [x] Add deterministic document ingest with source/span hashes and locators.
- [x] Add immutable HTTPS source synchronization and safe ZIP handling.
- [x] Add reviewed workflow and requirement evidence mapping.
- [x] Add KMUH default sources, workflow, form sets, and conservative
  requirements.
- [x] Add human-login Browser MCP discovery and safety gates.
- [x] Add sanitized, content-addressed page mappings and reviewed control
  bindings.
- [x] Fail closed when the legacy KFSYSCC generator is asked to produce KMUH
  forms.
- [x] Add a GitHub Pages documentation site and deployment workflow.
- [x] Push `agent/kmuh-irb-harness`, open draft PR #2, and enable workflow-based
  GitHub Pages for the repository.
- [x] Add a human-confirmed local asset import path with signature checks,
  immutable evidence manifests, and explicit source-revision handling.
- [x] Add Python 3.10/3.12 CI for locked install, lint, format, type checks,
  regression tests, and package build.
- [x] Make multi-organization compilation deterministic, content-stable,
  deduplicated, and free of workstation absolute paths.
- [x] Validate actual media signatures for both online and offline declared
  assets.
- [x] Gate browser draft writes through reviewed requirement/control bindings,
  live page/type checks, and value-type validation.
- [x] Let a newly compiled organization add or explicitly replace workflow
  transitions from human definitions and verified evidence spans.
- [x] Establish the SSH reverse-forward listener and distinguish it from Chrome
  CDP metadata readiness in `browser-status`.
- [x] Restrict Browser MCP CDP attachment to credential-free HTTP loopback
  origins.
- [x] Validate bounded Chrome discovery metadata and its same-port loopback
  browser WebSocket before Playwright attachment.
- [x] Generate DOM-unique selectors for repeated form groups and align reviewed
  binding eligibility with the controls the draft runtime can actually fill.
- [x] Scope page inventory to a selected contract website before reading titles,
  defaulting to KMUH eIRB without exposing unrelated profile tabs.

## Doing

- [ ] Start desktop Chrome with its dedicated profile and CDP port 9222; the
  reverse SSH listener is already established.
- [ ] Review and merge draft PR #2 so the first Pages deployment can run from
  `main`.

## Next

- [ ] Perform a value-free inventory of the real logged-in KMUH eIRB pages.
- [ ] Retrieve or import official KMUH documents and verify exact evidence spans.
- [ ] Add real KMUH form/browser adapters only after those sources and controls
  are reviewed.
