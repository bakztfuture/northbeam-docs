# Northbeam Docs

An internal docs studio: writers edit a single draft per article, publish it as an immutable numbered snapshot, and public readers only ever see the live snapshot.

- `backend/`: FastAPI + SQLite API (`/api/admin`, `/api/public`, `/api/health`)
- `frontend/`: Vue 3 + TypeScript + Vite writer studio and public reader

## Prerequisites

- Python 3.12+
- Node 20.19+ (with npm)

## Getting started

Installing, testing, and running the app are each a single command, run from the repository root.

**Install everything** (backend virtualenv and dependencies, plus the frontend's npm packages):

```bash
make setup
```

**Run all tests:**

```bash
make test
```

**Start the dev servers** (API on http://localhost:8000 and frontend on http://localhost:5173, which proxies `/api` to the API; Ctrl+C stops both):

```bash
make dev
```

If your default `python3` is older than 3.12, install with `make setup PYTHON=python3.13`.

### Linting and formatting

Ruff lints and formats the backend; ESLint and Prettier do the same for the frontend.

**Check everything** (changes nothing; fails on any problem):

```bash
make lint
```

**Fix and format everything:**

```bash
make format
```

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `DOCS_DB_PATH` | `backend/data/docs.sqlite3` | SQLite file; its parent directory is created if missing |
| `DOCS_DB_BUSY_TIMEOUT_MS` | `5000` | How long a write waits for the database lock before returning 503 |

## Data model

Two SQLite tables. The single mutable draft lives on the article row; published snapshots are a separate, append-only table.

| Table | Holds |
|---|---|
| `articles` | `id`, `slug` (unique, fixed after creation), `status` (`draft`, `published`, or `unpublished`), the draft (`draft_title`, `draft_body`, `draft_tags` as a JSON array), `draft_version` (incremented on every draft change, used for conflict detection), `last_published_version_number` (the snapshot counter), `current_published_version_id` (**the pointer**: the most recently published snapshot), `published_at` (first publication time), `created_at`, `updated_at` |
| `article_versions` | One immutable snapshot per publish: `id`, `article_id`, `version_number`, `title`, `body`, `tags`, `created_at` |

**Why this shape.** Drafts and published content are kept physically separate, so editing a draft can never change what readers see: the public API reads only from `article_versions`, through the pointer, and never selects a draft column. The draft sits on the article row rather than in its own table because there is exactly one draft per article, so a separate table would add a join without adding a guarantee. Snapshots get their own append-only table because every publish must leave behind a record that can be inspected and restored but never edited. With this split, each lifecycle rule maps onto a database constraint or trigger (table below), so the rules hold even against a bug in the application or a write made with direct SQL. The database has no ORM and only two tables, because the constraints are the point and the SQL is small enough to read directly.

The lifecycle rules are enforced by the database itself, not only by application code:

| Invariant | Enforced by |
|---|---|
| Snapshots are immutable, live or historical | A `BEFORE UPDATE` trigger on `article_versions` that rejects every update |
| Status, pointer, and `published_at` are consistent: a draft has neither; a published or unpublished article has both | A table `CHECK` on `articles` |
| The pointer names a snapshot of the same article | Composite foreign key `(id, current_published_version_id)` → `article_versions (article_id, id)` |
| The pointed-to snapshot cannot be deleted | `ON DELETE RESTRICT` on that foreign key |
| Snapshot numbers are unique per article | `UNIQUE (article_id, version_number)` |
| Snapshot numbers are never reused, even after deletions | The monotonic `last_published_version_number` counter, advanced inside the publish transaction (never `MAX(version_number) + 1`) |
| Slugs are unique | `UNIQUE (slug)` |
| Tags are a JSON array | `CHECK (json_valid(...) AND json_type(...) = 'array')`; the API validates the contents |

Every write runs in one `BEGIN IMMEDIATE` transaction that commits or fully rolls back. Connections use `foreign_keys = ON` and `synchronous = FULL`, and the database file is in WAL mode.

**Why unpublish keeps the pointer.** Unpublish changes only the status. The pointer and `published_at` stay, so the database keeps a record of what was last live, and the last published snapshot stays protected by the same `ON DELETE RESTRICT`. The pointer, not the highest version number, is the only source of truth for what is live: public reads join on it and filter on `status = 'published'`.

**Schema setup, not migrations.** `backend/app/migrations/` holds a single file, `0001_initial_schema.sql`. It is applied on every startup, and every statement uses `IF NOT EXISTS`, so re-running it changes nothing. There is no migration runner yet: nothing records which files have run. To change the schema of an existing local database, delete the database file and restart. The next step would be a small runner that applies numbered files in order and tracks progress in `PRAGMA user_version`.

## Errors

Every known error has one flat JSON shape; `message` is omitted when there is nothing to add:

```json
{"code": 409, "title": "Draft conflict", "message": "The draft changed since it was loaded."}
```

| Status | Title | When |
|---|---|---|
| 404 | e.g. "Article not found" | An unknown article, snapshot, or public slug |
| 409 | e.g. "Draft conflict" | A stale `expectedDraftVersion`, or a state that does not allow the action |
| 409 | "Slug already exists" | The slug is taken, including when two creates race and the database rejects the second |
| 409 | "Snapshot is in use" | The database refuses to delete the snapshot an article points to |
| 422 | (FastAPI's default `{"detail": [...]}` body, unchanged) | Invalid body, unknown field, or malformed id |
| 503 | "Database unavailable" | The database cannot be opened or initialized. Every endpoint, including `GET /api/health`, returns this, and the app recovers on the next request once the file can be opened, with no restart |
| 503 | "Service temporarily unavailable" ("The database is busy.") | A write could not get the database lock within `DOCS_DB_BUSY_TIMEOUT_MS`. No `Retry-After` header is sent and nothing retries automatically |
| 500 | "Internal server error" | Anything unexpected. The body is only `code` and `title`; the details are logged |

The two 503s differ: "Database unavailable" means the database could not be opened at all, while "Service temporarily unavailable" means it is open but a write timed out waiting for the lock.

CHECK and trigger violations return 500 on purpose: the API never attempts those writes, so reaching one means there is a bug, and a 409 would hide it. A failed write is always rolled back, and its lock released, before the error response is sent.

## A trade-off made under time pressure

The frontend has no automated tests: no unit tests and no end-to-end tests. With limited time, I spent the testing effort where a bug would do the most damage, the content lifecycle. The backend suite covers every invariant and edge case against a real SQLite file: snapshot immutability, the atomic publish with a forced rollback, stale-draft conflicts, the protected snapshot, and concurrent publishes. Because those rules are enforced in the database and API, a UI bug can show the wrong thing or block an action, but it can't publish a draft by accident or corrupt a snapshot. So the frontend is checked by hand instead: the publish confirmation, disabling Publish while there are unsaved edits, the busy flag, conflict handling, and Markdown safety. The cost is that a UI regression, or a mismatch between what the frontend sends and what the API expects, only shows up if someone walks through the app. With more time, I'd start with Vitest unit tests for the composables (`useArticleEditor` above all), since that's where the frontend logic lives: dirty tracking, save routing, the busy flag, and what a 409 or 503 means for the page. Those tests need no rendering and run in milliseconds. Then I'd add a few Playwright end-to-end tests against the real backend for the paths that matter most: create, save, publish (confirming and cancelling), restore, unpublish, and two tabs conflicting on the same draft. That way the full path from browser to database is checked on every change, not just during a manual walkthrough.
