# Tasks

## 1. Project scaffolding

- [ ] 1.1 Create `backend/` with `pyproject.toml` (FastAPI, Uvicorn, Pydantic; dev: pytest, httpx), `app/main.py` with `create_app(settings)`, and `app/config.py` with `Settings` (`DOCS_DB_PATH`, `DOCS_DB_BUSY_TIMEOUT_MS` defaulting to 5000); verify `GET /api/health` returns 200 in a smoke test
- [ ] 1.2 Create `frontend/` with Vite + Vue 3 + TypeScript, Vue Router, markdown-it, and Vitest, plus a dev proxy from `/api` to `localhost:8000`; verify `npm run build` and `npm run test` succeed
- [ ] 1.3 Add a root `Makefile` with `setup`, `dev`, `test`, and `test-fe` targets; verify each runs from a clean checkout
- [ ] 1.4 Start `README.md` with prerequisites (Python 3.12+, Node 20.19+), setup, run, and test commands; verify the documented commands match the Makefile

## 2. Database schema and transactions

- [ ] 2.1 Write `app/schema.sql` (both tables, CHECK constraints, composite FK with `ON DELETE RESTRICT`, immutability trigger) and `init_schema()` that applies it and sets WAL; verify a fresh database file is created on startup and `PRAGMA journal_mode` reports `wal`
- [ ] 2.2 Implement `connect()` (with `isolation_level=None`, `foreign_keys = ON`, `busy_timeout` from settings) and the `get_db` per-request dependency; verify with a test that a new connection reports foreign keys on and the configured busy timeout
- [ ] 2.3 Implement `write_txn(conn)` (`BEGIN IMMEDIATE`, then `COMMIT`, or `ROLLBACK` and re-raise on any exception); verify with tests that an exception inside it leaves no rows behind and that a second connection can write immediately afterwards
- [ ] 2.4 **Mandatory:** add the direct-SQL immutability test: an `UPDATE` on both a live and a historical snapshot, run on a plain connection, is rejected, and both rows are unchanged. Seed the snapshots with direct inserts until the publish endpoint exists in group 5, which extends the test to the public read
- [ ] 2.5 Add constraint tests on plain connections: `published` with no pointer is rejected, `unpublished` with no pointer is rejected, a pointer to another article's snapshot is rejected, a direct delete of the pointed-to snapshot is rejected, and malformed JSON tags are rejected; verify all pass
- [ ] 2.6 Add a "Data model" section to the README covering both tables, the invariant-to-constraint mapping, and why unpublish keeps the pointer; verify it matches `schema.sql`

## 3. Error handling and validation

- [ ] 3.1 Implement `AppError` and its handler returning flat `{code, title, message?}`; verify a test route raising `AppError(409, ...)` returns that body, without `message` when it is `None`
- [ ] 3.2 Implement the sqlite error mapping (slug UNIQUE to 409, FK failure to 409, locked/busy to 503 with `Retry-After: 1`, everything else to 500) and the generic 500 handler, which logs the traceback; verify with tests that each case returns the right status and that a 500 body contains only `code` and `title`
- [ ] 3.3 Implement Pydantic request and response models (camelCase aliases, slug regex, non-blank title and body, title max 200, tag normalization and limit, `expectedDraftVersion >= 1`, `extra="forbid"` on draft saves, UUID path ids); verify with unit tests for each rule, including that a malformed id returns the default 422
- [ ] 3.4 Add an "Errors" section to the README describing the error format and status codes; verify the examples match the test expectations

## 4. Article authoring

- [ ] 4.1 Implement `POST /api/admin/articles` (status `draft`, draft version 1, no snapshot); verify with tests for a successful create (201), duplicate slug (409, nothing created), invalid slug or blank body (422), and the new article returning 404 publicly once group 7 lands
- [ ] 4.2 Implement `GET /api/admin/articles` and `GET /api/admin/articles/{id}`; verify with tests that the list includes every status and that an unknown id returns 404
- [ ] 4.3 Implement `PATCH /api/admin/articles/{id}/draft` with compare-and-set on `draft_version`; verify with tests that a save increments the version, a stale version returns 409 and keeps the first writer's content (EC-01), a missing article returns 404, a stray `slug` returns 422, and no snapshot is created

## 5. Publishing and unpublishing

- [ ] 5.1 Implement `POST /api/admin/articles/{id}/publish` as one `write_txn` (check version, INSERT snapshot, UPDATE article with `COALESCE(published_at, now)`); verify with tests that the first publish gives v1 and status `published`, the snapshot equals the saved draft, and the draft, draft version, and `updated_at` are unchanged
- [ ] 5.2 Verify the publish rules with tests: a stale `expectedDraftVersion` returns 409 with no snapshot (EC-02), a republish keeps `published_at` and earlier snapshots, and publishing unchanged content creates a new snapshot (EC-22)
- [ ] 5.3 **Mandatory:** add the publish rollback test using `app.dependency_overrides[get_db]` with a test-only connection wrapper that raises on the article state UPDATE; verify through a fresh connection that there is no new snapshot, status, pointer, `published_at`, counter, and draft are unchanged, and a later normal publish gets the expected next number
- [ ] 5.4 Add the concurrent-publish test (two threads with their own connections, synchronised by a barrier); verify both succeed with consecutive numbers and the pointer names the higher one (EC-04)
- [ ] 5.5 Implement `POST /api/admin/articles/{id}/unpublish` as a status-only change; verify with tests that it returns 200, keeps the pointer, `published_at`, and every snapshot, returns 409 for draft-only and already-unpublished articles (EC-20), and that a republish after unpublish creates the next snapshot and keeps `published_at` (EC-21)
- [ ] 5.6 Extend the immutability test from 2.4 to snapshots created through the publish endpoint and to the public content; verify it passes

## 6. Version history

- [ ] 6.1 Implement `GET /api/admin/articles/{id}/versions` (newest first, with `isCurrent`) and `GET /api/admin/articles/{id}/versions/{versionId}`; verify with tests for ordering, the `isCurrent` flag, an empty list for draft-only articles, 404 for an unknown article, and 404 for a snapshot of another article (EC-17)
- [ ] 6.2 Implement `POST .../versions/{versionId}/restore` with compare-and-set; verify with tests that the draft equals the snapshot, the version is incremented, the snapshot count and contents are unchanged, the public content is unchanged (EC-11), a stale version returns 409 (EC-12), and a missing snapshot returns 404
- [ ] 6.3 Implement `DELETE .../versions/{versionId}`; verify with tests that deleting a historical snapshot returns 204 and removes only it (EC-08), deleting the live snapshot returns 409 (EC-07), deleting the pointed-to snapshot of an unpublished article returns 409 (EC-10), deleting the old snapshot after a republish moves the pointer returns 204, and a missing snapshot returns 404
- [ ] 6.4 Add the number-reuse test: delete the highest non-pointed-to snapshot, publish, and verify the new number is one higher than the counter, not reused (EC-13)
- [ ] 6.5 Add a README note on the delete rule: the last published snapshot cannot be deleted while unpublished, and the workaround is to republish then delete; verify it matches the 6.3 behavior

## 7. Public reader API

- [ ] 7.1 Implement `GET /api/public/articles` (published only, title and tags from the live snapshot, `publishedAt`, newest first); verify with tests that draft and unpublished articles are excluded, saved draft edits do not appear, and the first publication time is shown after a republish
- [ ] 7.2 Implement `GET /api/public/articles/{slug}` from the live snapshot; verify with tests that it returns snapshot content after the draft is edited (EC-06), returns the new content after a republish, and returns an identical 404 for draft-only (EC-14), unpublished (EC-09, EC-15), and unknown slugs

## 8. Durability and locking

- [ ] 8.1 Add the lock-exhaustion test: a second connection holds `BEGIN IMMEDIATE` and the app uses a busy timeout of about 100 ms; verify a draft save returns 503 with `Retry-After`, the draft is unchanged, and a save succeeds once the lock is released (EC-19)
- [ ] 8.2 Add the restart test: create, edit, and publish with one app instance, then build a new instance on the same file; verify every article, draft, snapshot, and publication state reads back unchanged (EC-29)
- [ ] 8.3 Verify `make test` runs the whole backend suite with one command and passes

## 9. Shared frontend foundations

- [ ] 9.1 Implement the typed API client and TS types in `src/api/`, throwing `ApiError` with `code`, `title`, and `message`; verify with a Vitest test that a 409 response becomes an `ApiError` with code 409
- [ ] 9.2 Implement `src/lib/markdown.ts` (one markdown-it instance, `html: false`, safe link validation); verify with (FE) Vitest tests for each supported element, raw HTML not rendered, and `javascript:` links neutralized
- [ ] 9.3 Set up routes (`/`, `/articles/:slug`, `/studio`, `/studio/new`, `/studio/articles/:id`) and a shared layout with links between the studio and the public site; verify each route loads in the browser

## 10. Writer UI

- [ ] 10.1 Build the studio article list (title, slug, status, "New article" button); verify in the browser that all statuses are shown
- [ ] 10.2 Build the create form held locally, whose first save calls `POST` and then switches to the editor; verify in the browser that an abandoned form stores nothing and that a duplicate slug shows an error and keeps the typed content
- [ ] 10.3 Build the editor (title, body, tags, read-only slug, status, draft version, `publishedAt`, Save, live preview); verify in the browser that saving increments the version and that the preview sends no requests
- [ ] 10.4 **Highlighted:** implement `isDirty` (comparing the form to the last saved draft) and disable Publish while dirty, with the hint "Save your changes before publishing"; verify with an (FE) Vitest test that editing disables Publish, and that saving or reverting the edit enables it again
- [ ] 10.5 Add leave-page protection (`onBeforeRouteLeave` and `beforeunload`) when dirty; verify in the browser that navigating away asks for confirmation and staying keeps the edits
- [ ] 10.6 Add Publish and Unpublish controls (Unpublish only when `published`), refreshing the article and history afterwards; verify in the browser that the status and history update
- [ ] 10.7 Add the 409 conflict banner for save, restore, and publish, which keeps the form content and offers "Reload latest" behind a confirmation; verify in the browser with two tabs on the same article
- [ ] 10.8 Build the version history panel (newest first, current marked, view rendered, restore with confirmation when dirty, delete with confirmation, Delete unavailable with an explanation on the pointed-to snapshot); verify in the browser against EC-07, EC-08, EC-10, and EC-11

## 11. Public reader UI

- [ ] 11.1 Build the public list page (title, tags, publication date) and the article page (rendered snapshot body), with a "not found" page on 404; verify in the browser that an unpublished article's URL shows "not found"

## 12. Final integration

- [ ] 12.1 Complete the README with how to use the studio, the tradeoffs paragraph (unpublish pointer, no publish-state counter, SQLite single writer, no draft history, no overall request timeout, no migrations), and what is missing or next; verify every section the brief requires is present
- [ ] 12.2 From a fresh clone, run `make setup`, `make test`, `make test-fe`, and `make dev`, and walk through create, edit, publish, edit again, view public, restore, unpublish, delete; verify every step behaves as the specs describe

## Workflow follow-up

- Commit the planning artifacts before starting group 1, so the history shows the spec first.
- Commit roughly once per task group, with messages that name the group.
- Archive the change with `openspec archive add-docs-studio` once all tasks are done, so the specs move into `openspec/specs/`.
