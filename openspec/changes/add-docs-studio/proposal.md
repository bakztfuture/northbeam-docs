# Proposal

## Why

Northbeam's internal writers need to author documentation articles without accidentally changing what public readers see, and they need a safety net when a publish goes wrong. Today there is no system: drafts and published content must be separated so that editing never silently alters live content, and every publish must leave behind an immutable, inspectable snapshot that can be restored from.

## What Changes

- New Python backend (FastAPI + Pydantic) backed by a two-table SQLite database (`articles`, `article_versions`) that persists across restarts.
- Writer API (`/api/admin`, 10 endpoints): create an article, list and read articles, save the draft, publish, unpublish, list/view version history, restore a version into the draft, and delete a version.
- Public API (`/api/public`, 2 endpoints): list published articles and read one by slug, always from its live snapshot; draft-only and unpublished articles return 404.
- Lifecycle invariants enforced in the database itself, not only in application code:
  - snapshots are immutable (an `UPDATE` trigger rejects any change);
  - status, live-snapshot pointer, and `published_at` can only exist in legal combinations (CHECK constraint);
  - the snapshot the article points to cannot be deleted (`ON DELETE RESTRICT` composite foreign key);
  - publish is one `BEGIN IMMEDIATE` transaction, so it fully succeeds or fully rolls back.
- Optimistic concurrency on the draft: save, restore, and publish carry `expectedDraftVersion`; a stale request returns 409 instead of overwriting newer content.
- Unpublish is a status change only: the live-snapshot pointer and `published_at` are kept, so the last published snapshot stays protected until a later publish moves the pointer.
- Centralized error handling: one flat `{code, title, message?}` shape for known errors, expected database errors mapped to 409/503, everything unexpected returned as a generic 500.
- New Vue 3 + TypeScript + Vite frontend: a writer UI (article list, create form, editor with Markdown preview, publish controls, version history panel) and a public reader UI (list + article page), sharing one safe Markdown renderer.
- The writer UI disables Publish while the editor has unsaved changes, because publish snapshots the **saved** draft, not the editor contents.
- Automated backend tests for every lifecycle invariant, runnable with one command, including a direct-SQL immutability test and a publish-rollback test that injects a failure into the real transaction.

## Capabilities

### New Capabilities

- `article-authoring`: creating articles and editing their single mutable draft, including slug rules, input validation, and optimistic concurrency on draft writes.
- `article-publishing`: publishing the saved draft as a new immutable numbered snapshot, republishing, unpublishing, and the atomicity and state-consistency guarantees around them.
- `version-history`: listing and viewing snapshots, restoring a snapshot into the draft, deleting snapshots, and protection of the snapshot the article points to.
- `public-reader`: anonymous listing and reading of published articles from their live snapshot, and hiding everything else behind 404.
- `api-errors`: the shared error response format, mapping of expected database failures (constraint conflicts, lock exhaustion), and safe handling of unexpected errors.
- `markdown-rendering`: client-side rendering of stored Markdown for preview, history, and public pages, with raw HTML disabled and unsafe links blocked.
- `writer-ui`: the internal writer interface: article list, create form, editor, unsaved-change protection, conflict handling, and the version history panel.

### Modified Capabilities

None. This is the first change in the project.

## Impact

- **New code:** `backend/` (FastAPI app, SQLite schema and connection setup, services, tests) and `frontend/` (Vue 3 app).
- **New dependencies:** backend: FastAPI, Uvicorn, Pydantic, pytest, httpx (test client); the stdlib `sqlite3` module is used directly with no ORM. Frontend: Vue 3, Vue Router, Vite, TypeScript, markdown-it, Vitest.
- **Data:** a local SQLite file (ignored by git), created and migrated on startup.
- **Out of scope:** authentication and roles, WYSIWYG or rich Markdown directives, media uploads, search and pagination, caching, deployment and CI/CD, draft revision history, a concurrency counter for publish/unpublish state, idempotent publish, and other stretch goals.
