# Active Context

Last updated: 2026-07-15

## Current Goal

Refactor the fork into a multi-organization, citation-ready IRB harness:

1. Convert organization-provided documents into evidence-tracked contracts.
2. Keep KMUH as the bundled default without reusing KFSYSCC form identities.
3. Attach a Browser MCP to a human-authenticated KMUH eIRB session.
4. Maintain README, GitHub Pages, memory-bank, segmented commits, and pushes as
   the implementation evolves.

## Current State

- The organization contract, source sync, evidence mapping, requirement mapping,
  sanitized page mapping, and reviewed portal-control binding are implemented.
- The KMUH default declares 11 sources, 8 form sets, 16 workflow events, and 9
  conservative requirements that remain `needs_evidence`.
- The Browser MCP exposes discovery and reviewed draft/read operations, with no
  submit, approval, withdrawal, termination, or delete tool. Draft writes must
  resolve a content-addressed requirement/control binding and recheck the live
  page, field metadata, value type, runtime switch, and human confirmation.
- Generic document compilation now uses content-derived source IDs and portable
  `urn:sha256:` identities, deduplicates identical bytes, omits absolute paths
  and runtime timestamps, and produces deterministic outputs.
- Declared official assets can now be imported from human-confirmed local copies
  when the execution host has no route to the institution; the same immutable
  evidence manifest and `needs_mapping` gate are preserved.
- Online retrieval now applies the same PDF/DOCX/ZIP byte-signature checks, so
  an HTML error response cannot be accepted as a declared official document.
- The dependency-free GitHub Pages site is committed and Pages is configured for
  workflow deployment at `https://u9401066.github.io/irb-in-hurry/`; first
  deployment waits for PR #2 to merge to `main`.
- Branch `agent/kmuh-irb-harness` is pushed with segmented commits and draft PR
  `https://github.com/u9401066/irb-in-hurry/pull/2` is open.

## Current Blockers

- Codex runs on Remote SSH host `affineserver` (`192.168.1.111`). Desktop Chrome
  is on SSH client `192.168.1.2`; the client must add
  `RemoteForward 127.0.0.1:9222 127.0.0.1:9222` and reconnect.
- The Remote SSH host cannot retrieve the official KMUH source bytes. Evidence
  hashes and locators must stay unverified until routing is available or the
  official files are copied into the workspace and processed with `import-local`.

## Next Verification

1. Confirm `uv run irb-contract browser-status` reports `available: true`.
2. List open KMUH pages, check login state, and perform value-free discovery.
3. Write a content-addressed page map and bind only human-reviewed controls.
4. Retrieve or import official source bytes and map reviewed evidence spans.
