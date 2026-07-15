# Organization Contract Architecture

## Target model

The harness separates five concerns that were previously mixed together:

1. Organization-provided source documents and their immutable identity.
2. Human-reviewed workflow, requirement, and form applicability rules.
3. Evidence bindings that prove where each reviewed claim came from.
4. Document rendering adapters.
5. Browser adapters for organization portals.

The bundled default is `irb_harness.contracts/kmuh.yml`. A workspace may override
it with `organizations/kmuh/contract.yml`, or pass an explicit contract path.

## Evidence invariants

`irb-contract compile` never edits source documents. For every input it records:

- source URI and byte size;
- SHA-256 of the original bytes;
- SHA-256 of extracted text;
- stable source and span IDs;
- line and character offsets;
- short surrounding context.

Contract compilation does not infer institutional requirements. It produces a
`draft` with `rule_inference: not_performed`; a human maps workflow and explicit
requirements to evidence spans before the contract becomes authoritative.

## Official-source synchronization

`irb-contract sync-sources` retrieves only URLs already declared in the selected
contract. It requires HTTPS, rejects embedded credentials and cross-host
redirects, imposes byte/member limits, and stores response bodies by SHA-256 in
the ignored `.irb-source-cache/` directory. ZIP expansion rejects traversal,
symlinks, duplicate paths, and unbounded output.

Each run produces an immutable JSON evidence manifest. A successful transport
sets `evidence_status: retrieved_needs_rule_mapping`; it never upgrades evidence
to `verified`. The generated workspace override is
`organizations/<organization>/contract.yml`. An existing override is not changed
unless `--update-output` is explicit, and the previous bytes are first preserved
as a content-addressed cache snapshot.

If an execution host cannot reach the declared HTTPS source, `irb-contract
import-local` accepts one file that a human downloaded from that source. It
requires explicit source-identity confirmation, rejects symlinks and invalid
PDF/DOCX/ZIP signatures, detects files that change during copying, and writes the
same immutable cache and evidence-manifest shape as online synchronization. The
manifest records `human_provided_local_copy` without persisting the source
machine's absolute path or raw filename. A changed contract SHA-256 requires an
explicit revision flag and preserves the superseded hash plus contract snapshot.
Local acquisition never skips the `needs_mapping` review state.

Workflow transitions and institutional requirements carry `evidence_refs`.
Before retrieval, a reference is `needs_retrieval`; source synchronization
advances it only to `needs_mapping`.
After a human chooses the relevant spans, `irb-contract map-evidence` checks the
source byte hash, manifest hash, and every span ID before changing that one
reference to `verified`. The selected span text hashes and manifest hash are
also preserved in `evidence_bindings`; the command never chooses spans itself.

## Reviewed requirements

A `ContractRequirement` expresses one reviewable claim, such as a required
document, deadline, manual step, eligibility condition, or portal field. Its
`applies_to` block may select submission types, review tracks, and workflow
events. `irb-contract requirements` filters these explicit dimensions; it does
not execute hidden policy logic.

`irb-contract map-requirement` takes a human-authored YAML definition and
human-selected evidence spans. It strips any caller-supplied status or evidence
references, verifies the selected source bytes and locator hashes, then writes a
canonical `requirement` evidence binding. Replacing a requirement is explicit,
and the decision record preserves the definition and manifest hashes with
`automated_rule_inference: false`.

The bundled KMUH requirements are conservative placeholders with
`needs_evidence`; they are not presented as verified hospital policy until the
official assets are retrieved and reviewed.

## Reviewed portal bindings

A portal requirement first declares a stable `data_path`. After a human maps an
authenticated page, `irb-contract bind-requirement-control` verifies the
content-addressed page map and binds that requirement to one control ID. The
contract stores the mapping hash, selector, and risk class, but not raw labels or
field values. Only input, select, and textarea controls are eligible; hidden,
password, submit, disabled, and destructive controls are rejected. A claimed
portal mapping without its matching reviewed binding fails contract validation.

## Compatibility boundary

The historical `scripts/generators` modules encode KFSYSCC SF forms. They remain
available during migration, but a KMUH contract must not alias those form IDs.
New rendering adapters will consume `FormSet` entries and organization templates
instead of post-processing KFSYSCC DOCX text.
