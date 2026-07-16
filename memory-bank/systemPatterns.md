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
- **Portable compilation:** content-derived source IDs and `urn:sha256:` URIs
  make compile outputs deterministic without workstation absolute paths.
- **Symmetric media validation:** online downloads and human-provided local
  copies both validate PDF/DOCX/ZIP bytes, not only filenames or headers.
- **Layered bridge readiness:** Browser status distinguishes the SSH TCP listener
  from valid Chrome CDP metadata. Attachment requires bounded JSON and a browser
  WebSocket on the same loopback port; opaque debugger URLs are never returned.
- **DOM-unique browser identities:** IDs and names are selectors only when they
  match one live control; repeated groups use verified ancestor/sibling paths,
  and contract binding rejects anything the draft runtime cannot safely fill.
- **Contract-scoped inventory:** Browser tab enumeration filters allowed hosts
  before reading titles, so one organization's MCP cannot inventory unrelated
  pages in the attached dedicated profile.

## Evidence State Machine

```text
needs_retrieval -> needs_mapping -> verified
```

Retrieval alone can only reach `needs_mapping`. A human-selected span plus source,
manifest, and span-hash verification is required for `verified`.

## Browser Safety Pattern

```text
human login -> session gate -> value-free discovery -> hashed page map
            -> human review -> requirement/control binding
            -> live fingerprint/type recheck -> gated draft action
```

Submission and destructive actions have no MCP tool.

## Documentation Pattern

- `README.md` and `README.zh-TW.md`: repository entry points.
- `docs/`: detailed architecture and operator guides.
- `site/`: concise GitHub Pages explanation and live readiness labels.
- `memory-bank/`: current goals, blockers, decisions, and progress.
