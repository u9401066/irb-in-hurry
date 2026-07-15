# Product Context

## Overview

IRB-in-Hurry reduces repetitive institutional review board paperwork while
preserving human ethics judgment. The refactored product accepts institution
documents, produces a traceable contract, and lets document/browser adapters
consume only reviewed claims.

## Users

- Investigators and study coordinators preparing submissions.
- IRB operations staff validating institutional procedures and templates.
- Developers adapting the harness to another hospital or review board.

## Core Capabilities

- PDF, DOCX, HTML, Markdown, and text ingest with stable locators and hashes.
- Immutable official-source synchronization and evidence manifests.
- Human-reviewed workflow and requirement evidence bindings.
- Explicit applicability queries by submission type, review track, and event.
- Human-login Browser MCP with sanitized page mapping and gated draft actions.
- Historical KFSYSCC form generation retained behind a clear compatibility
  boundary.

## Non-goals

- Deciding whether a study is ethical or approving it.
- Inventing institutional rules from source text.
- Handling user credentials.
- Automatically submitting, withdrawing, terminating, deleting, or approving an
  eIRB case.
