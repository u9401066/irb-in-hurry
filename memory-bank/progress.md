# Progress

Last updated: 2026-07-15

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

## Doing

- [ ] Establish the desktop-Chrome reverse SSH bridge on port 9222.
- [ ] Review and merge draft PR #2 so the first Pages deployment can run from
  `main`.

## Next

- [ ] Perform a value-free inventory of the real logged-in KMUH eIRB pages.
- [ ] Retrieve or import official KMUH documents and verify exact evidence spans.
- [ ] Add real KMUH form/browser adapters only after those sources and controls
  are reviewed.
