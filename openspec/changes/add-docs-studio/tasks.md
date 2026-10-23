# Tasks

Six groups, built layer by layer. Each group is one commit and is reviewable on its own: it lands its code, its tests, and any README section it owns. Edge cases (EC-*) and invariants are listed in design Decision 9.

## 1. Foundations: scaffold, database, errors

- [x] 1.1 Scaffold the project
  - `backend/` with `pyproject.toml` (FastAPI, Uvicorn, Pydantic; dev: pytest, httpx), `app/main.py` with `create_app(settings)` and a `lifespan` handler, empty `repositories/`, `migrations/`, `services/`, and `routes/` packages, and `app/config.py` with `Settings` (`DOCS_DB_PATH`, `DOCS_DB_BUSY_TIMEOUT_MS`, default 5000)
  - `frontend/` with Vite + Vue 3 + TypeScript, Vue Router, and markdown-it (no CSS preprocessor), empty `services/`, `composables/`, `views/`, `components/`, and `styles/` folders, and a dev proxy from `/api` to `localhost:8000`
  - Root `Makefile` with `setup`, `dev`, and `test`; `README.md` with prerequisites (Python 3.12+, Node 20.19+) and those commands
  - Verify: `make setup` then `make dev` starts both apps from a clean checkout
- [x] 1.2 Database layer: `app/migrations/0001_initial_schema.sql` and `app/repositories/database.py`
  - Schema: both tables, CHECK constraints, composite FK with `ON DELETE RESTRICT`, immutability trigger, all `IF NOT EXISTS` (not a migration handler)
  - `init_db()` (sets WAL, runs the schema file), `connect()` (`isolation_level=None`, `foreign_keys = ON`, `busy_timeout`, `synchronous = FULL`, parent directory created), the `get_db` dependency, and `write_txn()` (`BEGIN IMMEDIATE`, then `COMMIT`, or `ROLLBACK`, then raise the mapped AppError or re-raise)
- [x] 1.3 Errors, validation, and the health check
  - `AppError`, one subclass per known error, and the flat `{code, title, message?}` handler; SQLite error mapping in `write_txn` (slug UNIQUE to 409 "Slug already exists", any FK failure to 409 "Snapshot is in use", locked/busy to 503 "Service temporarily unavailable" with no `Retry-After`, everything else to a logged generic 500)
  - Pydantic models (design Decision 5 naming): request models `CreateArticleRequest`, `SaveDraftRequest`, `PublishArticleRequest`, `RestoreSnapshotRequest`, and `HealthStatus` as the health check's `response_model`; camelCase aliases; slug regex, max 100; non-blank title, max 200; non-blank body, max 50,000; tags trimmed, lowercased, de-duplicated, at most 20, each at most 100; `expectedDraftVersion >= 1`; `extra="forbid"` on draft saves; UUID path ids
  - "Database unavailable" gate: `lifespan` records whether `init_db()` succeeded; `get_db` retries it and raises `DatabaseUnavailableError`; `GET /api/health`
- [x] 1.4 Foundation tests (`make test`): only the most critical checks; the rest are tested through the real endpoints in groups 2 and 3. Tests live in `tests/api/` (through HTTP) and `tests/database/` (plain SQL)
  - Health returns 200 `{"status": "ok"}`
  - With `DOCS_DB_PATH` pointing at a directory, health returns 503 "Database unavailable" with no path in the body, and returns 200 once the directory is removed, without a restart (EC-34)
  - **Mandatory:** a direct-SQL `UPDATE` on a live and a historical snapshot is rejected and both rows are unchanged (EC-05; seeded with direct inserts for now)
  - The database's own refusals, which no endpoint can trigger: a `published` article with no pointer, a pointer to another article's snapshot (EC-28), and a direct delete of the pointed-to snapshot are each rejected
- [x] 1.5 README: "Data model" (tables, invariant-to-constraint mapping, why unpublish keeps the pointer, `migrations/` holds only the initial schema) and "Errors" (the format and every status code, including the two different 503s)
- [x] 1.6 Linting and formatting
  - Backend: Ruff in the `dev` extras, configured in `pyproject.toml` (line length 120; default rules plus `I`, `B`, `UP`), used for both linting and formatting
  - Frontend: ESLint (flat config with `eslint-plugin-vue` and `@vue/eslint-config-typescript`) and Prettier, with `@vue/eslint-config-prettier` so the two do not conflict; `lint` and `format` scripts in `package.json`
  - Makefile: `make lint` (Ruff check, Ruff format check, ESLint, Prettier check; fails on any problem) and `make format` (Ruff fix and format, ESLint fix, Prettier write); README lists both
  - Verify: after `make format`, `make lint` passes on the whole repository and `make test` still passes

## 2. Backend: authoring and publishing

- [x] 2.1 Authoring endpoints in `routes/admin.py`, with SQL in `repositories/articles.py` and rules in `services/authoring.py`. Each route declares the response model from design Decision 5:
  - `create_article`: `POST /api/admin/articles`, `CreateArticleRequest` → 201 `AdminArticle`
  - `list_articles`: `GET /api/admin/articles` → `list[ArticleListItem]`, newest `updatedAt` first
  - `get_article`: `GET /api/admin/articles/{articleId}` → `AdminArticle`
  - `save_draft`: `PATCH /api/admin/articles/{articleId}/draft`, `SaveDraftRequest` → `AdminArticle`, with compare-and-set on `draft_version`
  - Response models `AdminArticle` (with nested `draft`) and `ArticleListItem` in the Responses section of `models.py`; the admin router included in `routes/__init__.py` under `/admin`
- [x] 2.2 Publishing endpoints in `routes/admin.py`, with rules in `services/publishing.py`
  - `publish_article`: `POST .../publish`, `PublishArticleRequest` → 201 `PublishedArticle` (`article` plus the new `snapshot`), as one `write_txn`: check the version, INSERT the snapshot, UPDATE the article with `COALESCE(published_at, now)`
  - `unpublish_article`: `POST .../unpublish` → `AdminArticle`, as a status-only change
  - Response models `PublishedArticle` and `Snapshot`
- [x] 2.3 Authoring and publishing tests
  - Authoring: create gives a draft at version 1 with no snapshot; duplicate slug 409 (EC-16); the list includes every status; unknown id 404; save increments the version; stale save 409 "Draft conflict" (EC-01); stray `slug` 422 (EC-36); one basic test of an invalid create asserting the full Pydantic 422 body (EC-18); create, read, and save return exactly the `AdminArticle` fields; the list returns `ArticleListItem` rows, newest `updatedAt` first, and a publish or unpublish does not reorder it
  - Publishing: publish returns `PublishedArticle` whose `snapshot` is the new snapshot and whose `article` points at it; first publish gives v1 and leaves the draft, draft version, and `updated_at` unchanged; stale version 409 with no snapshot (EC-02); republish keeps `published_at`; unchanged content still creates a snapshot (EC-22)
  - Unpublishing: keeps the pointer, `published_at`, and every snapshot; 409 for draft-only (EC-20) and already-unpublished (EC-30) articles; republish after unpublish (EC-21)
  - **Mandatory:** rollback test with `app.dependency_overrides[get_db]` and a wrapper that raises on the article UPDATE; nothing changes, and the next publish gets the expected number (EC-03)
  - Concurrency: two simultaneous publishes get consecutive numbers (EC-04); a simultaneous publish and unpublish leave a consistent row (EC-33)
  - Extend the immutability test to snapshots created by publishing

## 3. Backend: history, public reader, integration

- [x] 3.1 History endpoints in `routes/admin.py`, with rules in `services/history.py`
  - `list_snapshots`: `GET .../snapshots` → `list[SnapshotListItem]`, newest first, with `isCurrent`
  - `get_snapshot`: `GET .../snapshots/{snapshotId}` → `Snapshot`
  - `restore_snapshot`: `POST .../snapshots/{snapshotId}/restore`, `RestoreSnapshotRequest` → `AdminArticle`, with compare-and-set
  - `delete_snapshot`: `DELETE .../snapshots/{snapshotId}` → 204, refused for the pointed-to snapshot
  - Response model `SnapshotListItem`
- [x] 3.2 Public endpoints in `routes/public.py`, with rules in `services/public.py`; the public router included in `routes/__init__.py` under `/public`
  - `list_public_articles`: `GET /api/public/articles` → `list[PublicArticleListItem]`, published only, title and tags from the live snapshot, newest `publishedAt` first
  - `get_public_article`: `GET /api/public/articles/{slug}` → `PublicArticle`
  - Response models `PublicArticle` and `PublicArticleListItem`, with no draft fields
- [x] 3.3 History, public, and integration tests
  - History: list and view return `SnapshotListItem` and `Snapshot`; restore returns `AdminArticle`; ordering, `isCurrent`, an empty list for a draft-only article, 404 for an unknown article; restore updates only the draft (EC-11); stale restore 409 (EC-12); restore then publish creates a new snapshot (EC-32); delete a historical snapshot (EC-08), the live snapshot 409 (EC-07), the pointed-to snapshot while unpublished 409 (EC-10), a historical snapshot while unpublished 204 (EC-42), the old snapshot after a republish 204 (EC-31); numbers are never reused (EC-13); wrong-article or missing snapshot 404 (EC-17)
  - Public: snapshot content after a draft edit (EC-06); new content after a republish; an identical 404 for draft-only, unpublished, and unknown slugs (EC-09, EC-14, EC-15, EC-37); the list excludes non-published articles, shows snapshot title and tags rather than saved draft edits, shows the first publication time; the 404 for an unpublished article has the flat `{code, title}` body (EC-23); both public responses contain exactly the documented fields and no draft fields
  - Extend the immutability test to the public content: after the rejected direct updates, the public read still returns the live snapshot's original content
  - Golden path: one article from create to republish through the HTTP API, checking public visibility, history, pointer, `published_at`, `updated_at`, and `draft_version` after every step (design Decision 7)
  - Lock exhaustion returns 503 with no `Retry-After` header and leaves the draft unchanged, and a save succeeds once the lock is released (EC-19); data survives a restart (EC-29)
  - `make test` runs the whole backend suite in one command and passes
- [x] 3.4 README note on the delete rule: the last published snapshot cannot be deleted while unpublished; the workaround is to republish, then delete

## 4. Frontend foundations

- [ ] 4.1 Styles in `src/styles/`: `tokens.css` (colors, spacer scale, type scale with line heights and weights, radii, content width and gutter, all as custom properties on `:root`), `grid.css` (12-column grid, no breakpoints), `typography.css` (base and Markdown styles from tokens only), and `main.css`; README "Styling" section listing the tokens and the tokens-only rule
- [ ] 4.2 `src/services/` (`http.ts` throwing `ApiError`, `adminArticles.ts`, `publicArticles.ts`, and `types.ts`, which mirrors the response shapes in design Decision 5) and `src/lib/markdown.ts` (one markdown-it instance, `html: false`, safe links) with the `MarkdownView` component
- [ ] 4.3 The reusable `ConfirmModal` (props `open`, `title`, `message`, `confirmLabel`, `cancelLabel`, `tone`; emits `confirm` and `cancel`; Escape and a backdrop click cancel), the routes, the shared layout, and a page-level 503 error display that does not retry
- [ ] 4.4 Check in the browser: `npm run build` succeeds; each route loads; a duplicate-slug create surfaces as an `ApiError` with code 409; supported Markdown renders while raw HTML and `javascript:` links do not; the modal shows its props and emits the right event for each way of closing

## 5. Frontend: writer and public UI

- [ ] 5.1 `useArticleList` and the studio list view (title, slug, status, "New article")
- [ ] 5.2 `useArticleEditor` (`saved`, `form`, `isDirty`, the snapshot list, conflict and error state, the page-level busy flag, the pending `confirmation`, and every action, calling only `src/services/`), the create and editor views, and `ArticleForm` with a live preview. Save calls `POST` on the first save, then `PATCH`
- [ ] 5.3 **Highlighted:** the publish flow
  - Publish is disabled while `isDirty`, with "Save your changes before publishing"
  - Publish opens `ConfirmModal`, and only Confirm sends the request; Unpublish appears only when `published`
  - The busy flag is set when a request starts (after confirmation) and cleared in `finally`; while busy, every action control is disabled and the active one shows progress
- [ ] 5.4 The 409 conflict banner with "Reload latest" behind the modal, and `VersionHistoryPanel` (view, restore with confirmation when there are unsaved edits, delete with confirmation, Delete unavailable on the pointed-to snapshot); after a publish or a delete, the editor reloads the snapshot list so `isCurrent` is never stale
- [ ] 5.5 `usePublicArticles` and the public list and article pages, with a "not found" page
- [ ] 5.6 Check:
  - no view or component imports from `src/services/`
  - a search of `src/components/` and `src/views/` finds no hex colors, `rgb(`, `px` or `rem` literals, or `--` definitions
  - in the browser, every (FE) scenario in the specs works, including a first save switching to the editor, an abandoned new form storing nothing, a duplicate slug keeping the typed content, a conflict between two tabs, preview without requests (EC-25), snapshot view (EC-26), Publish disabled while dirty (EC-39), Restore unavailable during a save (EC-40), and cancelling the publish modal (EC-41)

## 6. README and final check

- [ ] 6.1 Complete the README: how to use the studio, the invariants and edge-case tables (design Decision 9), every tradeoff from the design's Risks / Trade-offs section (including at least one paragraph on a tradeoff made under time pressure and what would change with more time), and what is missing or next
- [ ] 6.2 From a fresh clone, run `make setup`, `make lint`, `make test`, and `make dev`, and walk through create, edit, publish (confirm and cancel), edit again, view public, restore, unpublish, and delete; every step behaves as the specs describe

## Workflow follow-up

- One commit per group, with a message that names the group.
- Archive the change with `openspec archive add-docs-studio` once all tasks are done, so the specs move into `openspec/specs/`.
