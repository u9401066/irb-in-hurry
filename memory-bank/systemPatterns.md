# System Patterns

## Architectural Patterns

- **Organization contract:** institutional behavior is explicit data, not a set
  of scattered `if institution == ...` branches.
- **Content addressing:** original documents, evidence manifests, contract
  snapshots, and browser maps use SHA-256 identities.
- **Ports and adapters:** domain validation stays pure; file/network/browser I/O
  lives in infrastructure and application layers.
- **Fail closed:** unknown sources, stale hashes, incomplete bindings, unsafe
  controls, and missing human confirmation are rejected.

## Evidence State Machine

```text
needs_retrieval -> needs_mapping -> verified
```

Retrieval alone can only reach `needs_mapping`. A human-selected span plus source,
manifest, and span-hash verification is required for `verified`.

## Browser Safety Pattern

```text
human login -> session gate -> value-free discovery -> hashed page map
            -> human review -> requirement/control binding -> gated draft action
```

Submission and destructive actions have no MCP tool.

## Documentation Pattern

- `README.md` and `README.zh-TW.md`: repository entry points.
- `docs/`: detailed architecture and operator guides.
- `site/`: concise GitHub Pages explanation and live readiness labels.
- `memory-bank/`: current goals, blockers, decisions, and progress.
