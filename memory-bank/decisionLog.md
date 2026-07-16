# Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-07-15 | Use an organization contract instead of institution conditionals in generators. | Different IRBs have different workflow, evidence, forms, and websites; these differences need explicit data and provenance. |
| 2026-07-15 | Make KMUH the bundled default while preserving KFSYSCC as a named compatibility layer. | Prevents existing SF forms from being mislabeled as official KMUH forms. |
| 2026-07-15 | Compilation performs no institutional rule inference. | Human review is required before a source span becomes an authoritative workflow or requirement claim. |
| 2026-07-15 | Store sources and page maps by SHA-256. | Content addressing makes stale or substituted evidence detectable. |
| 2026-07-15 | Require human login and omit submit/destructive MCP tools. | Credentials and irreversible IRB actions remain outside the automation trust boundary. |
| 2026-07-15 | Publish a dependency-free static GitHub Pages site. | Keeps documentation deployment small, auditable, and independent of a JavaScript build chain. |
| 2026-07-15 | Develop on `agent/kmuh-irb-harness` with segmented commits. | The starting worktree contains unrelated assistant-harness assets that must not be staged silently. |
| 2026-07-15 | Permit human-confirmed local copies of declared assets. | Remote execution hosts may not share institutional routing; offline acquisition must retain media validation, immutable hashes, acquisition provenance, and the same human mapping gate. |
| 2026-07-15 | Make local compilation content-stable and path-free. | Organization contracts and evidence indexes must be portable across workstations and reproducible from identical bytes. |
| 2026-07-15 | Require every browser draft write to resolve a reviewed portal requirement binding. | An arbitrary selector bypasses the contract boundary; mapping, control, field/value type, live fingerprint, runtime switch, and exact human confirmation must all agree. |
| 2026-07-15 | Add workflow transitions only from explicit definitions plus verified spans. | A newly compiled organization needs a supported path to its first workflow event without either guessing rules or requiring untracked manual YAML edits. |
| 2026-07-16 | Accept Browser MCP CDP endpoints only on credential-free HTTP loopback origins. | Human-login attachment should travel through a local/reverse-forwarded trust boundary, never a remotely exposed browser debugger. |
