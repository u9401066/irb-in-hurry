# Architecture Memory

## System Shape

The fork uses a DDD-style boundary under `src/irb_harness/`:

- `domain`: pure organization contracts, requirements, evidence references, and
  safety invariants;
- `application`: compile, sync, evidence mapping, requirement mapping, and
  portal-control binding use cases;
- `infrastructure`: document ingest, immutable retrieval, browser attachment,
  and web action policy;
- `presentation`: `irb-contract` CLI and `irb-web-mcp` server;
- `contracts`: bundled organization defaults, currently KMUH.

## Trust Boundaries

- Source transport success is not semantic verification.
- Automated compilation extracts and hashes; it does not infer policy.
- Humans choose evidence spans and define institutional requirements.
- Browser login and all submission/destructive actions remain human-owned.
- Page mappings exclude values, body text, case links, and raw labels.

## Compatibility Boundary

Historical `scripts/generators` modules remain KFSYSCC-specific. A KMUH
configuration fails closed instead of aliasing KFSYSCC SF form IDs.
