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
