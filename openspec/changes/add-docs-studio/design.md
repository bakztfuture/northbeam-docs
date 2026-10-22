# Design

## Context

The repository is greenfield: it contains only the OpenSpec scaffold. Motivation and scope are in `proposal.md`; required behavior is in the seven spec deltas under `specs/`. This document covers how the system is built.

Fixed constraints:

- Python backend (FastAPI + Pydantic), Vue 3 + TypeScript + Vite frontend, SQLite for storage.
- One trusted writer, no authentication.
- Must run from a clean checkout with a short setup command, and tests must run with one command.
- The lifecycle invariants are what is being evaluated, so they are enforced by the database wherever SQLite allows it, with application checks on top for clear error messages.

## Goals / Non-Goals

**Goals:**

- Every invariant in the specs is either enforced by a database constraint or trigger, or performed inside a single write transaction, and is covered by an automated test.
- Tests exercise the real code paths and a real SQLite file, not mocks of the data layer.
- A small, readable codebase: one SQL schema file, thin route handlers, one service module per capability.

**Non-Goals:**

- Schema migrations tooling. The schema is created on startup with `CREATE ... IF NOT EXISTS`; a migration tool would be the next step for a real product.
- An ORM or query builder. The SQL is small and the constraints are the point, so it is written directly.
- Frontend state-management libraries, component libraries, or styling frameworks.
- Running behind multiple worker processes. SQLite serializes writes; the design is correct with several workers but is only tested with one.

## Decisions

### 1. Repository layout and commands

```
backend/
  app/
    main.py            create_app(settings): FastAPI app, routers, error handlers
    config.py          Settings: DB path, busy timeout (env-configurable)
    db.py              connect(), get_db dependency, write_txn(), init_schema()
    schema.sql         tables, constraints, trigger
    errors.py          AppError, handlers, sqlite error mapping
    models.py          Pydantic request/response models
    services/          authoring.py, publishing.py, history.py, public.py
    routes/            admin.py, public.py
  tests/
  pyproject.toml
frontend/
  src/
    api/               typed client + TS types
    lib/markdown.ts    the one shared renderer
    views/             studio and public pages
    components/
  package.json
Makefile               setup, dev, test, test-fe
```

`make setup` creates `backend/.venv` with `python3 -m venv` and installs the backend, then runs `npm install` in `frontend/`. `make test` runs the backend test suite (`pytest`), which is the single command for the lifecycle tests. `make test-fe` runs the (FE) Vitest tests separately. `make dev` starts Uvicorn on port 8000 and Vite on port 5173 with a dev proxy from `/api` to the backend.

*Alternatives:* `uv` is faster and nicer but adds a prerequisite a reviewer may not have; plain `venv` + `pip` needs only Python 3.12+. A Docker setup was rejected as unnecessary for SQLite.

### 2. Data model

Two tables. The draft lives on the article row; snapshots are a separate append-only table.

```
articles                                   article_versions
+--------------------------------------+   +---------------------------+
| id                 TEXT PK (uuid)    |   | id           TEXT PK      |
| slug               TEXT UNIQUE       |   | article_id   TEXT FK ---->+--> articles.id
| status             draft|published|  |   | version_number INTEGER    |
|                    unpublished       |   | title, body  TEXT         |
| draft_title, draft_body   TEXT       |   | tags         TEXT (json)  |
| draft_tags         TEXT (json array) |   | created_at   TEXT         |
| draft_version      INTEGER >= 1      |   | UNIQUE(article_id,        |
| last_published_version_number >= 0   |   |        version_number)    |
| current_published_version_id  ------+-->| UNIQUE(article_id, id)    |
| published_at, created_at, updated_at |   +---------------------------+
+--------------------------------------+
  FK (id, current_published_version_id)
     -> article_versions(article_id, id) ON DELETE RESTRICT
```

The schema (`backend/app/schema.sql`):

```sql
CREATE TABLE IF NOT EXISTS articles (
    id TEXT PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'published', 'unpublished')),
    draft_title TEXT NOT NULL,
    draft_body TEXT NOT NULL,
    draft_tags TEXT NOT NULL DEFAULT '[]'
        CHECK (json_valid(draft_tags) AND json_type(draft_tags) = 'array'),
    draft_version INTEGER NOT NULL DEFAULT 1 CHECK (draft_version >= 1),
    last_published_version_number INTEGER NOT NULL DEFAULT 0
        CHECK (last_published_version_number >= 0),
    current_published_version_id TEXT,
    published_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (id, current_published_version_id)
        REFERENCES article_versions (article_id, id) ON DELETE RESTRICT,
    CHECK (
        (status = 'draft'
            AND current_published_version_id IS NULL
            AND published_at IS NULL)
        OR
        (status IN ('published', 'unpublished')
            AND current_published_version_id IS NOT NULL
            AND published_at IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS article_versions (
    id TEXT PRIMARY KEY,
    article_id TEXT NOT NULL REFERENCES articles (id),
    version_number INTEGER NOT NULL CHECK (version_number >= 1),
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '[]'
        CHECK (json_valid(tags) AND json_type(tags) = 'array'),
    created_at TEXT NOT NULL,
    UNIQUE (article_id, version_number),
    UNIQUE (article_id, id)
);

CREATE TRIGGER IF NOT EXISTS prevent_article_version_update
BEFORE UPDATE ON article_versions
BEGIN
    SELECT RAISE(ABORT, 'Published snapshots are immutable');
END;
```

How each invariant maps to the schema:

| Invariant (spec) | Enforced by |
|---|---|
| Snapshots are immutable | `BEFORE UPDATE` trigger on `article_versions`, for every row |
| Status, pointer, and `published_at` are consistent | Table CHECK on `articles` |
| The pointer names a snapshot of the same article | Composite FK `(id, current_published_version_id)` to `UNIQUE(article_id, id)` |
| The pointed-to snapshot cannot be deleted | `ON DELETE RESTRICT` on that FK |
| Snapshot numbers are unique per article | `UNIQUE(article_id, version_number)` |
| Snapshot numbers are never reused | Monotonic `last_published_version_number` counter, advanced in the publish transaction |
| Slugs are unique | `UNIQUE(slug)` |

*Key decision: unpublish keeps the pointer.* `unpublished` requires a non-null pointer, so unpublish is the single-column change the brief describes, and the last published snapshot stays protected by the same `ON DELETE RESTRICT`. The cost is that a writer who wants to delete that snapshot must publish again first, which moves the pointer. This is documented in the README.

*Rule: the pointer is the only source of truth for what is live.* The highest-numbered snapshot is not necessarily the live one: after a restore and republish, or once snapshots are deleted, the two can differ. So no query ever infers "live" from `MAX(version_number)` or from snapshot creation time. Public reads join on `current_published_version_id` and filter on `status = 'published'`. The `isCurrent` flag in the history list compares each snapshot's id with the pointer.

*Alternatives:*
- Clearing the pointer on unpublish, which makes every snapshot deletable afterwards. Rejected because it loses the record of what was last live and allows deleting the last published snapshot, which the brief requires to be preserved.
- Computing the next number as `MAX(version_number) + 1`. Rejected because it reuses a number after the highest snapshot is deleted.
- A separate `drafts` table. Rejected: there is exactly one draft per article, so a second table adds a join without adding a guarantee.

Other storage choices:
- UUIDs are generated in Python (`uuid4`) and stored as text.
- Timestamps are UTC ISO 8601 with milliseconds, which sort correctly as text.
- Tags are a JSON array of strings. The CHECK validates the shape and Pydantic validates the contents.

### 3. Connections and transactions

- **One connection per request.** It is provided by a FastAPI dependency, `get_db`, which opens the connection, sets `foreign_keys = ON` and `busy_timeout`, yields it, and closes it afterwards. Services receive the connection as a parameter and never open their own. Besides keeping services simple, this is what lets tests substitute the connection (Decision 7).
- **WAL mode.** It is set once in `init_schema()` at startup, because the setting is stored in the database file. Readers never block the writer, and the writer never blocks readers.
- **Connections are opened with `isolation_level=None`**, so the `sqlite3` module never starts a transaction implicitly. The one place transactions begin is `write_txn(conn)`, a context manager:

```
with write_txn(conn):        # BEGIN IMMEDIATE  (take the write lock now)
    ... reads + writes ...   # all statements see a stable state
                             # on success: COMMIT
                             # on any exception: ROLLBACK, then re-raise
```

  Every write operation (create, save, publish, unpublish, restore, delete) runs inside exactly one `write_txn`. Reads run without a transaction, since each read endpoint's queries do not need a shared snapshot of the data.
- **Why `BEGIN IMMEDIATE`:** taking the write lock at `BEGIN` rather than at the first write means the read-then-write sequence (check the draft version, then insert) cannot be interleaved with another writer. It also means lock waits happen at one predictable point, which the busy timeout governs.
- **Busy timeout.** `busy_timeout` comes from `Settings` (default 5000 ms, env `DOCS_DB_BUSY_TIMEOUT_MS`), so tests can use about 100 ms. The database path is also configurable (`DOCS_DB_PATH`, default `backend/data/docs.sqlite3`).

### 4. Write operations

Each service function is one `write_txn`. Inside it, application checks come first, so the client gets a specific error; the constraints in Decision 2 are the backstop.

**Save draft and restore** use compare-and-set in one statement:

```sql
UPDATE articles
SET draft_title = ?, draft_body = ?, draft_tags = ?,
    draft_version = draft_version + 1, updated_at = ?
WHERE id = ? AND draft_version = ?;
```

If no row changed, the service looks up the article to tell the cases apart: a missing article is 404, an existing one means the version was stale (409). Restore first reads the snapshot with `WHERE id = ? AND article_id = ?` (404 if absent), then runs the same UPDATE with the snapshot's content. It never writes `article_versions`.

**Publish:**

```
BEGIN IMMEDIATE
  SELECT article                      404 if missing
  check draft_version == expected     409 if stale
  n = last_published_version_number + 1
  INSERT article_versions (new id, n, draft_title, draft_body, draft_tags)
  UPDATE articles SET status = 'published',
                      current_published_version_id = new id,
                      last_published_version_number = n,
                      published_at = COALESCE(published_at, now)
         WHERE id = ?
COMMIT                                any exception -> ROLLBACK
```

- **Statement order:** the INSERT must come before the UPDATE, because the composite FK requires the snapshot to exist before the article can point at it.
- **What publish leaves alone:** it does not change `draft_version` or `updated_at`, because the draft is not modified.
- **Concurrent publishes:** two of them for the same article serialize on the write lock. The second one reads the counter the first one committed, so they get consecutive numbers.

**Unpublish:**

```sql
UPDATE articles SET status = 'unpublished' WHERE id = ? AND status = 'published';
```

If no row changed, the service returns 404 when the article is missing and 409 otherwise.

**Delete snapshot:** inside a `write_txn`, the service:

1. Reads the snapshot with `WHERE id = ? AND article_id = ?`, returning 404 if it is absent.
2. Reads the article's pointer, returning 409 if it names this snapshot.
3. Deletes the snapshot.

If a race ever got past step 2, the RESTRICT FK would still refuse the delete, and the error mapping (Decision 6) would turn that into a 409.

*Alternative considered:* computing publish inside a single `INSERT ... SELECT` statement. Rejected because the explicit steps are easier to read and to test, and `BEGIN IMMEDIATE` already makes them atomic.

### 5. API shape

The JSON uses camelCase (Pydantic `alias_generator=to_camel`, `populate_by_name=True`). Path ids are typed as `UUID`, so a malformed id is a 422 and a well-formed unknown id is a 404.

| Method | Path | Body | Success |
|---|---|---|---|
| GET | `/api/admin/articles` | | 200 list of article summaries |
| POST | `/api/admin/articles` | `title, slug, body, tags` | 201 article |
| GET | `/api/admin/articles/{id}` | | 200 article |
| PATCH | `/api/admin/articles/{id}/draft` | `title, body, tags, expectedDraftVersion` | 200 article |
| POST | `/api/admin/articles/{id}/publish` | `expectedDraftVersion` | 201 `{article, version}` |
| POST | `/api/admin/articles/{id}/unpublish` | | 200 article |
| GET | `/api/admin/articles/{id}/versions` | | 200 version summaries, newest first, with `isCurrent` |
| GET | `/api/admin/articles/{id}/versions/{versionId}` | | 200 version |
| POST | `/api/admin/articles/{id}/versions/{versionId}/restore` | `expectedDraftVersion` | 200 article |
| DELETE | `/api/admin/articles/{id}/versions/{versionId}` | | 204 |
| GET | `/api/public/articles` | | 200 `[{slug, title, tags, publishedAt}]`, newest `publishedAt` first |
| GET | `/api/public/articles/{slug}` | | 200 `{slug, title, body, tags, publishedAt}` |

- **The admin article object** contains: `id, slug, status, draft {title, body, tags}, draftVersion, currentPublishedVersionId, publishedAt, createdAt, updatedAt`.
- **The public endpoints** join `articles` to `article_versions` on the pointer, filter on `status = 'published'`, and select only snapshot columns plus `slug` and `published_at`. The draft columns are never selected, so they cannot leak.
- **Health check.** `GET /api/health` returns 200 for smoke tests and `make dev` checks. It is not one of the 12 endpoints above and touches no data.
- **Draft saves reject unknown fields** (`extra="forbid"`), so a stray `slug` returns 422 rather than being silently ignored.

### 6. Validation and errors

**Pydantic models** enforce the input rules from the `article-authoring` spec:

- slug: `^[a-z0-9]+(-[a-z0-9]+)*$`, 1 to 100 characters;
- title: stripped, 1 to 200 characters;
- body: at least one non-whitespace character;
- tags: each one stripped, lowercased, and non-empty, at most 20, duplicates removed while keeping first-seen order;
- `expectedDraftVersion`: `int >= 1`.

FastAPI's default 422 handler is left unchanged.

**Known errors.** `AppError(code, title, message=None)` is the one application exception class. A single handler renders it as `{"code", "title", "message"?}`, with `message` omitted when it is `None`.

**SQLite error mapping** is done in one function, called by the generic exception handler, so routes have no try/except blocks:

| sqlite3 error | Message starts with | Response |
|---|---|---|
| `IntegrityError` | `UNIQUE constraint failed: articles.slug` | 409 "Slug already exists" |
| `IntegrityError` | `FOREIGN KEY constraint failed` (on a snapshot delete) | 409 "Snapshot is in use" |
| `OperationalError` | `database is locked` or `database is busy` | 503 "Service temporarily unavailable", no `Retry-After` |
| anything else, including CHECK and trigger aborts | | 500 |

CHECK and trigger failures stay 500 on purpose. The API never attempts those writes, so reaching one means there is a bug, and returning 409 would hide it.

**Unexpected errors.** Any other exception is logged with its traceback, and the response is only `{"code": 500, "title": "Internal server error"}`.

**Rollback before the response.** `write_txn` always rolls back before an exception leaves it, so by the time any handler runs, the transaction is already closed and the lock released.

*Alternative considered:* an exception subclass per error type (`NotFound`, `Conflict`). Rejected because one class with a code is enough for this size of API.

### 7. Testing approach

pytest; each test gets its own SQLite file in `tmp_path`. A fixture builds the app with `create_app(Settings(db_path=..., busy_timeout_ms=...))` and wraps it in FastAPI's `TestClient`. Tests go through HTTP unless a test is specifically about the database, in which case it uses a plain `sqlite3` connection to the same file.

- **Direct-SQL immutability** (mandatory): publish twice through the API so the article has a live snapshot and a historical one. Then, on a plain connection, run `UPDATE article_versions SET body = 'x' ...` against each. Each one must raise `sqlite3.IntegrityError` mentioning the immutability message. Re-reading both rows and the public endpoint must show unchanged content.
- **Publish rollback** (mandatory): uses `app.dependency_overrides[get_db]` so that the real publish route receives a test-only wrapper around a real connection. The wrapper forwards every call to SQLite, but raises when it sees the article state update statement (`UPDATE articles SET status = 'published'`). As a result, the real `BEGIN IMMEDIATE`, SELECT, and INSERT run against SQLite, and then the real `write_txn` rolls back. The test then removes the override and checks, through a fresh plain connection:
  - there is no new snapshot row;
  - status, pointer, `published_at`, the counter, and the draft are unchanged;
  - a normal publish afterwards gets the expected next number.
  No production code exists for this test; the only requirement it places on the design is Decision 3's "services get their connection from `get_db`".
- **Lock exhaustion (503):** a second plain connection holds `BEGIN IMMEDIATE`, while the app runs with a busy timeout of about 100 ms. A draft save must return 503, and after the lock is released, a save must succeed.
- **Concurrent publishes:** two threads, each with its own connection, call the publish service at the same moment, synchronised with a `threading.Barrier`. Both must succeed with consecutive numbers.
- **Restart durability:** create and publish through one app instance, dispose of it, build a new instance on the same file, and read everything back.
- **Constraint tests:** use plain connections to try the forbidden writes directly (a published article without a pointer; a pointer to another article's snapshot; deleting the pointed-to snapshot). Each must be rejected.
- **(FE) tests:** Vitest unit tests for `lib/markdown.ts` (supported elements, raw HTML disabled, `javascript:` links blocked) and for the editor's dirty-state logic that disables Publish. They are run by `make test-fe`, kept separate from the backend command.

*Alternatives for the rollback test:*
- A temporary trigger that aborts the UPDATE: works, but adds test-only database setup.
- Splitting publish into helpers that a test monkeypatches: changes production code's shape for testing.
- An optional failure-hook argument on publish: puts test-only code in the production signature.

The dependency override was chosen because production code stays unchanged and the real transaction is what rolls back.

### 8. Frontend

- **Routes:**

  | Path | Page |
  |---|---|
  | `/` | public list |
  | `/articles/:slug` | public article |
  | `/studio` | writer article list |
  | `/studio/new` | create form |
  | `/studio/articles/:id` | editor + history panel |

- **API client.** `src/api/` exports typed functions over `fetch`, with TS interfaces mirroring the API models. A non-2xx response throws an `ApiError` carrying `code`, `title` and `message`, so views can branch on 409 or 404.
- **State.** Each view owns its state with `ref`/`reactive`; there is no Pinia. The editor keeps two copies:
  - `saved`: the last draft returned by the API, plus its `draftVersion`;
  - `form`: what is in the inputs.

  `isDirty` is a computed comparison of `form` against `saved` on title, body, and tags. So typing a change and then reverting it clears the dirty state. After a successful save, both `form` and `saved` are replaced with the article the API returns, so normalized tags (for example "API" stored as "api") do not leave the editor looking dirty.
- **Save routing.** The editor has one Save action backed by two endpoints. With no article id yet (`/studio/new`), Save calls `POST /api/admin/articles`; on 201 the app takes the returned id and draft version and navigates to `/studio/articles/:id`. From then on, Save calls `PATCH /api/admin/articles/{id}/draft` with the loaded `expectedDraftVersion`. The endpoints stay separate because only create accepts a slug and checks it is unique, and only save checks the draft version.
- **Unsaved-change protection.** Publish is disabled when `isDirty` is true, with the hint "Save your changes before publishing". There is deliberately no leave-page warning; it is out of scope.
- **Conflicts.** A 409 from save, restore, or publish shows a banner, keeps `form` as it is, and offers "Reload latest". That action fetches the article and replaces both `form` and `saved`, after the writer confirms.
- **Markdown.** `lib/markdown.ts` exports one `markdown-it` instance with `html: false` and the default `validateLink`, which rejects `javascript:`, `vbscript:`, `file:`, and non-image `data:` URLs. It is used by the preview, snapshot view, and public article page. The output is inserted with `v-html` only from this renderer.

## Risks / Trade-offs

- [Unpublish keeps the pointer, so the last published snapshot can't be deleted while unpublished] → Documented in the README with the workaround: publish again (unchanged content is fine), which moves the pointer, then delete the old snapshot.
- [Publish and unpublish have no concurrency counter of their own; two writers' publish and unpublish decisions can override each other] → Publish does carry `expectedDraftVersion`, so nobody can publish content they haven't seen. Unpublish only acts on a `published` article and returns 409 otherwise, so a repeated unpublish fails visibly rather than silently. A separate state counter is listed as future work.
- [SQLite allows one writer at a time] → Fine for an internal tool with a handful of writers. Writes are short, and the busy timeout turns long waits into a 503. Postgres with row locks is the path for higher write volume.
- [Error mapping matches SQLite error message text] → The messages are stable across SQLite versions. The mapping is covered by tests for both the slug and the FK cases, so a change would fail the tests rather than silently returning 500.
- [No migration tooling; the schema is created on startup] → Acceptable for a first version with no deployed data. The README notes that changing the schema means deleting the local database file.
- [Publishing unchanged content creates duplicate snapshots] → Intended for now. Idempotent publish is a known stretch goal and is out of scope.
- [The rollback test recognises the UPDATE by its SQL text] → If the statement is reworded, the test fails loudly, because the publish then succeeds and the test's assertion that it failed breaks. So it cannot pass silently.
- [Only a single Uvicorn worker is tested] → Correctness comes from SQLite locking, not process memory, so more workers stay correct. This is documented but not tested.
- [Only the latest saved draft is stored; draft saves have no history] → Saving increments `draft_version` for concurrency but keeps no earlier draft. Published snapshots are the version history. An overwritten unpublished draft cannot be recovered, which is acceptable because the brief's safety net is about publishes. A "save as version" feature would be the extension.
- [No overall request timeout] → The only time limit is SQLite's busy timeout. It bounds how long a write waits for the lock (5 s by default), not how long a request takes. There is no HTTP deadline, no write queue, and no automatic retry. A request that cannot get the lock returns 503 without a `Retry-After` header, and the UI shows the error without retrying; the writer can simply try the action again. Writes are a few short statements, so a server-side deadline would add complexity without a real case to handle.
