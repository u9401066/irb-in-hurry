# KMUH eIRB Browser MCP

## Security model

The MCP server never receives or stores KMUH credentials. It attaches to a
visible Chromium session after a human signs in. Use a dedicated browser profile;
do not expose the CDP port beyond loopback.

Chrome 136 and later require `--remote-debugging-port` to be paired with a
non-default `--user-data-dir`. Start a separate profile on the desktop host,
for example:

```bash
google-chrome \
  --remote-debugging-address=127.0.0.1 \
  --remote-debugging-port=9222 \
  --user-data-dir="/absolute/private/path/kmuh-irb-browser-profile"
```

Then sign in manually and open:

```text
https://erec.kmuh.org.tw/RECManageSystem/Home/Index
```

If Codex runs in a container or remote environment, forward this loopback port
to the execution environment and configure the resulting endpoint:

```bash
export IRB_WEB_CDP_ENDPOINT=http://127.0.0.1:9222
uv run irb-contract browser-status
```

This workspace currently runs through VS Code Remote SSH. In that topology the
browser is on the SSH client and the MCP server is on the SSH host. Add a reverse
forward on the client and reconnect:

```sshconfig
Host your-irb-development-host
  RemoteForward 127.0.0.1:9222 127.0.0.1:9222
```

Equivalent one-off SSH syntax:

```bash
ssh -R 127.0.0.1:9222:127.0.0.1:9222 user@remote-host
```

Keep both ends bound to loopback. The reverse forward transports CDP only; the
human must still sign in inside the dedicated local Chrome profile.

The `RemoteForward` line must be written to the SSH **client's** configuration.
Editing `~/.ssh/config` from a Remote SSH terminal changes the remote host's
outbound SSH settings and cannot modify the already-established VS Code
connection. In VS Code, run `Remote-SSH: Open SSH Configuration File` on the
desktop, edit the same `Host` entry used to open the workspace, then reconnect.

If `browser-status` still reports `connection_refused`, verify on the remote
host that `127.0.0.1:9222` has a listener and confirm Chrome was started with
both `--remote-debugging-port=9222` and a non-default `--user-data-dir` before
the SSH connection was established.

Do not bind the debugging endpoint to `0.0.0.0` and do not reuse the everyday
Chrome profile.

## MCP tools

Start the stdio server with:

```bash
uv run irb-web-mcp
```

The repository includes `.vscode/mcp.json` for the native VS Code MCP provider.
The same fragment is available at `config/mcp.kmuh.example.json` for other clients.
When installing elsewhere, merge it into existing MCP settings; do not replace
unrelated servers.

The initial server exposes:

- `irb_contract_summary`: contract provenance and outstanding retrieval work;
- `irb_requirements`: applicable contract requirements and their evidence
  readiness, filtered by explicit submission/review/workflow dimensions;
- `irb_browser_bridge_status`: CDP reachability only;
- `irb_browser_list_pages`: hashed titles and redacted route shapes;
- `irb_site_session_status`: human-login gate state;
- `irb_discover_current_page`: form-control labels, selectors, required flags,
  and risk class, without field values, page titles, body text, or case-list links;
- `irb_sanitized_page_mapping`: keeps selectors and risk metadata while replacing
  raw labels with SHA-256 identities; it does not write a local file;
- `irb_click_reviewed_control`: clicks one control from a content-addressed
  mapping only after explicit confirmation and live fingerprint/risk rechecks;
- `irb_fill_draft_field`: one explicitly confirmed draft field only.

Draft writes require both `IRB_WEB_WRITE_MODE=draft` and explicit confirmation
for the exact field/value. Password, hidden, file, button, and submit controls are
rejected. No submit, approval, withdrawal, termination, or delete tool is exposed.

When more than one `erec.kmuh.org.tw` tab is open, first call
`irb_browser_list_pages` and pass its ephemeral `page_ref` (for example `c0p2`)
to the status, discovery, mapping, or draft-fill tool. This prevents a stale
login tab from being selected instead of the intended form. Login selectors are
considered only when visible; hidden template controls do not trigger a false
`human_login_required` result.

Reviewed read clicks are disabled by default. After inspecting the exact mapping
and control, start the server with `IRB_WEB_CLICK_MODE=reviewed`; each call must
still set `human_confirmed` for that control. The loader accepts only
`.irb-web-artifacts/<organization>/<site>/<mapping_sha256>.json`, verifies the
artifact hash, rejects stale live fingerprints, and refuses draft, submit, or
destructive risk. This switch does not enable draft field writes; those retain
the separate `IRB_WEB_WRITE_MODE=draft` gate.

## Discovery workflow

1. Human starts the dedicated browser and signs in.
2. Human opens the target eIRB page.
3. MCP checks `irb_site_session_status`, with `page_ref` when multiple tabs match.
4. MCP runs `irb_discover_current_page` and records the page fingerprint and
   value-free control map.
5. `uv run irb-contract map-page --site kmuh_eirb` writes a sanitized mapping
   below `.irb-web-artifacts/`; selectors remain usable, but raw labels are hashed.
6. A human reviews the mapping, identifies the `control_id`, and runs:

   ```bash
   uv run irb-contract bind-requirement-control \
     --contract organizations/kmuh/contract.yml \
     --requirement '<portal-field-requirement-id>' \
     --site kmuh_eirb \
     --mapping-sha256 '<mapping-sha256>' \
     --control-id '<control-id>' \
     --update-output
   ```

   This accepts only a predeclared `portal_field` requirement with a stable
   `data_path`, and never records raw labels or current field values.
7. The resulting contract binding remains content-addressed. A different live
   page fingerprint or control risk requires a new mapping and human review.
8. Mapping regression tests use synthetic HTML fixtures; real case content is
   never committed.
