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

- Every invariant in the specs is either enforced by a database constraint or trigger, or performed inside a single write transaction, and is covered by an automated test (see Decision 9). The one exception is the crash case (EC-35), which rests on SQLite's own guarantee.
- Tests exercise the real code paths and a real SQLite file, not mocks of the data layer.
- A small, readable codebase with clear layers: thin route handlers, services for business rules and transactions, and repositories for SQL.

**Non-Goals:**

- Migration handling. `app/migrations/` exists and holds the initial schema file, which is applied on startup, but there is no migration runner yet (Decision 3).
- An ORM or query builder. The SQL is small and the constraints are the point, so it is written directly.
- Frontend state-management libraries, component libraries, or styling frameworks. Styling is plain CSS (native custom properties and native nesting) with our own tokens; no preprocessor.
- Automated frontend tests, for now. The project's focus is the content lifecycle, so testing effort goes into thorough backend tests of every invariant and edge case instead. Scenarios marked (FE) in the specs are checked by hand in the browser.
- Running behind multiple worker processes. SQLite serializes writes; the design is correct with several workers but is only tested with one.

## Decisions

### 1. Repository layout and layers

```
backend/
  app/
    main.py              create_app(settings): FastAPI app, lifespan, routers, error handlers
    config.py            Settings: DB path, busy timeout (env-configurable)
    errors.py            AppError, handlers, sqlite error mapping
    models.py            Pydantic request/response models
    repositories/
      database.py        core DB wrappers: connect(), get_db dependency,
                         write_txn(), init_db()
      articles.py        SQL operations on articles and article_versions
    migrations/
      0001_initial_schema.sql   tables, constraints, trigger
    services/            authoring.py, publishing.py, history.py, public.py
    routes/              admin.py, public.py, health.py
  tests/
  pyproject.toml
frontend/
  src/
    services/            API calls only: http.ts (fetch + ApiError),
                         adminArticles.ts, publicArticles.ts, types.ts
    composables/         business logic and state: useArticleList,
                         useArticleEditor, usePublicArticles
    views/               pages: connect a composable to components
    components/          presentational: props in, events out
                         (ArticleForm, MarkdownView, VersionHistoryPanel,
                         ConfirmModal, StatusBadge, ErrorBanner)
    styles/              tokens.css, grid.css, typography.css, main.css
    lib/markdown.ts      the one shared renderer
  package.json
Makefile                 setup, dev, test
```

Each layer has one job, and calls only the layer below it:

```
routes/        HTTP only: parse the request (Pydantic), call a service,
   |           shape the response. No SQL, no business rules.
   v
services/      business rules: version checks, status checks, 404/409
   |           decisions. Owns the transaction: each write is one write_txn.
   v
repositories/  SQL only.
               - database.py: connections, transactions, schema setup.
               - articles.py: one function per query (e.g. insert_version,
                 update_draft_if_version, set_published, delete_version).
               Query functions in articles.py take a connection and return
               rows or counts; they never open transactions and never raise
               HTTP errors.
```

`get_db` in `database.py` is the one exception: it is the FastAPI dependency at the edge of the repositories layer, so it is where "the database cannot be opened" becomes `AppError(503, "Database unavailable")` (Decision 3).

Keeping transactions in services, not repositories, means one service call can combine several repository functions inside one `write_txn`. Publish is the main case: it needs an INSERT and an UPDATE that must succeed or fail together.

`make setup` creates `backend/.venv` with `python3 -m venv` and installs the backend, then runs `npm install` in `frontend/`. `make test` runs the backend test suite (`pytest`), which is the single command for the lifecycle tests. `make dev` starts Uvicorn on port 8000 and Vite on port 5173 with a dev proxy from `/api` to the backend.

*Alternatives:*
- `uv` is faster and nicer but adds a prerequisite a reviewer may not have; plain `venv` + `pip` needs only Python 3.12+.
- A Docker setup was rejected as unnecessary for SQLite.
- A single `db.py` holding connections and every query was rejected: with transactions, schema setup and about fifteen queries in one file, it would mix infrastructure with data access.

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

The initial schema file (`backend/app/migrations/0001_initial_schema.sql`). Every statement uses `IF NOT EXISTS`, so applying it on every startup is safe:

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

### 3. Connections, transactions, and schema setup

All of this lives in `repositories/database.py`.

- **One connection per request.** It is provided by a FastAPI dependency, `get_db`, which opens the connection, yields it, and closes it afterwards. Services receive the connection as a parameter and never open their own. Besides keeping services simple, this is what lets tests substitute the connection (Decision 7).
- **Connection settings.** `connect()` opens with `isolation_level=None`, so the `sqlite3` module never starts a transaction implicitly. It then sets three pragmas:
  - `foreign_keys = ON`;
  - `busy_timeout`;
  - `synchronous = FULL`, so a committed transaction survives a crash or power loss.
- **WAL mode.** It is set once by `init_db()` at startup, because the setting is stored in the database file. Readers never block the writer, and the writer never blocks readers.
- **Transactions.** The one place transactions begin is `write_txn(conn)`, a context manager:

```
with write_txn(conn):        # BEGIN IMMEDIATE  (take the write lock now)
    ... reads + writes ...   # all statements see a stable state
                             # on success: COMMIT
                             # on any exception: ROLLBACK, then re-raise
```

  Every write operation (create, save, publish, unpublish, restore, delete) runs inside exactly one `write_txn`. Reads run without a transaction, since each read endpoint's queries do not need a shared snapshot of the data.
- **Why `BEGIN IMMEDIATE`:** taking the write lock at `BEGIN` rather than at the first write means the read-then-write sequence (check the draft version, then insert) cannot be interleaved with another writer. It also means lock waits happen at one predictable point, which the busy timeout governs.
- **Crash safety.** SQLite's journal guarantees that a transaction that never committed is not visible after a restart, so a crash in the middle of a publish leaves the article exactly as it was before the publish. With `synchronous = FULL`, a transaction that did commit is still there after the restart. Together with the CHECK constraint, this rules out a stored state where the status and the pointer disagree.
- **Configuration.** `busy_timeout` comes from `Settings` (default 5000 ms, env `DOCS_DB_BUSY_TIMEOUT_MS`), so tests can use about 100 ms. The database path is also configurable (`DOCS_DB_PATH`, default `backend/data/docs.sqlite3`). The parent directory is created if it is missing.

**Schema setup (not a migration handler).** `backend/app/migrations/` holds a single file, `0001_initial_schema.sql`. On startup, `init_db(conn)` sets WAL mode and runs that file in one transaction. Because every statement uses `IF NOT EXISTS`, running it against an existing database changes nothing.

This is deliberately **not** a migration handler: nothing records which files have run, and only the initial file is applied. The folder exists so the schema lives in its own file and there is an obvious home for future changes. Until a runner exists, changing the schema of an existing local database means deleting the database file and letting startup recreate it. The natural next step is a small runner that applies numbered files in order and tracks progress in `PRAGMA user_version`.

**Database unavailable.** If the database cannot be opened, every endpoint must fail the same clear way instead of each one failing differently:

- **At startup**, FastAPI's `lifespan` handler calls `init_db()`. If that fails, for example because the path is unreadable or the file is not a database, the error is logged and `app.state.db_ready` stays `False`. The app still starts, so clients get a clear error response rather than "connection refused".
- **On every request**, `get_db` is the single gate. If `db_ready` is `False`, it first retries `init_db()`. Then it opens the connection. If either step raises `sqlite3.Error` or `OSError`, it raises `AppError(503, "Database unavailable", "The database could not be opened.")`. The real error and the path go to the log, never into the response.
- **Every router depends on `get_db`**, including health. So all endpoints are blocked uniformly by FastAPI's dependency system, and they recover on the next request once the database can be opened again, with no restart.
- **This is distinct from the "busy" 503** (Decision 6). "Database unavailable" means the database could not be opened at all; "Service temporarily unavailable" means a write timed out waiting for the lock.

### 4. Write operations

Each write is one service function that opens one `write_txn` and calls repository functions inside it. Inside the transaction, application checks come first, so the client gets a specific error; the constraints in Decision 2 are the backstop.

**Save draft and restore** use compare-and-set in one statement (`articles.update_draft_if_version`):

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
- **Concurrent publish and unpublish:** they also serialize on the write lock. Each one runs whole, one after the other, so whichever finishes last decides the final status. Every intermediate and final state satisfies the CHECK constraint.

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

| Method | Path | Body | Success | Errors |
|---|---|---|---|---|
| GET | `/api/admin/articles` | | 200 list of article summaries | |
| POST | `/api/admin/articles` | `title, slug, body, tags` | 201 article | 409 slug taken; 422 invalid body |
| GET | `/api/admin/articles/{id}` | | 200 article | 404 article; 422 malformed id |
| PATCH | `/api/admin/articles/{id}/draft` | `title, body, tags, expectedDraftVersion` | 200 article | 404 article; 409 stale draft version; 422 invalid body, unknown field such as `slug`, or malformed id |
| POST | `/api/admin/articles/{id}/publish` | `expectedDraftVersion` | 201 `{article, version}` | 404 article; 409 stale draft version; 422 invalid body or malformed id |
| POST | `/api/admin/articles/{id}/unpublish` | | 200 article | 404 article; 409 not `published`; 422 malformed id |
| GET | `/api/admin/articles/{id}/versions` | | 200 version summaries, newest first, with `isCurrent` | 404 article; 422 malformed id |
| GET | `/api/admin/articles/{id}/versions/{versionId}` | | 200 version | 404 article, snapshot, or snapshot of another article; 422 malformed id |
| POST | `/api/admin/articles/{id}/versions/{versionId}/restore` | `expectedDraftVersion` | 200 article | 404 article or snapshot; 409 stale draft version; 422 invalid body or malformed id |
| DELETE | `/api/admin/articles/{id}/versions/{versionId}` | | 204 | 404 article or snapshot; 409 snapshot the article points to; 422 malformed id |
| GET | `/api/public/articles` | | 200 `[{slug, title, tags, publishedAt}]`, newest `publishedAt` first | |
| GET | `/api/public/articles/{slug}` | | 200 `{slug, title, body, tags, publishedAt}` | 404 draft-only, unpublished, or unknown slug |

On top of the errors in the table:
- **Every endpoint** can return **503 "Database unavailable"** when the database cannot be opened (Decision 3), and **500** for unexpected errors.
- **Write endpoints** (POST, PATCH, DELETE) can also return **503 "Service temporarily unavailable"** when the write lock is not available within the busy timeout. Reads never wait for the lock in WAL mode.
- The public slug is not format-validated, so a malformed slug is simply an unknown slug: 404, never 422.

Notes:
- **The admin article object** contains: `id, slug, status, draft {title, body, tags}, draftVersion, currentPublishedVersionId, publishedAt, createdAt, updatedAt`.
- **The public endpoints** join `articles` to `article_versions` on the pointer, filter on `status = 'published'`, and select only snapshot columns plus `slug` and `published_at`. The draft columns are never selected, so they cannot leak.
- **Health check.** `GET /api/health` runs `SELECT 1` through `get_db`. It returns 200 when the database can be opened and 503 "Database unavailable" otherwise. It is not one of the 12 endpoints above and reads no article data.
- **Draft saves reject unknown fields** (`extra="forbid"`), so a stray `slug` returns 422 rather than being silently ignored.

### 6. Validation and errors

**Pydantic models** enforce the input rules from the `article-authoring` spec:

- slug: `^[a-z0-9]+(-[a-z0-9]+)*$`, 1 to 100 characters;
- title: stripped, 1 to 200 characters;
- body: at least one non-whitespace character;
- tags: each one stripped, lowercased, and non-empty, at most 20, duplicates removed while keeping first-seen order;
- `expectedDraftVersion`: `int >= 1`.

FastAPI's default 422 handler is left unchanged.

**Known errors.** `AppError(code, title, message=None)` is the one application exception class. A single handler renders it as `{"code", "title", "message"?}`, with `message` omitted when it is `None`. Services raise it for 404 and 409 decisions, and `get_db` raises it for "Database unavailable".

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
- **Schema setup:** a fresh file gets both tables and the trigger. Running `init_db()` again on a database with data leaves the data untouched.
- **Database unavailable:** `DOCS_DB_PATH` points at an existing directory, which SQLite cannot open as a file. An admin endpoint, a public endpoint, and the health check must all return 503 "Database unavailable", and the body must not contain the path. Then the directory is removed, and the next request succeeds without restarting the app.
- **Lock exhaustion (503):** a second plain connection holds `BEGIN IMMEDIATE`, while the app runs with a busy timeout of about 100 ms. A draft save must return 503 "Service temporarily unavailable", and after the lock is released, a save must succeed.
- **Concurrent publishes:** two threads, each with its own connection, call the publish service at the same moment, synchronised with a `threading.Barrier`. Both must succeed with consecutive numbers. A second run does the same with one publish and one unpublish, and checks the final row satisfies the status/pointer/`published_at` rules.
- **Restart durability:** create and publish through one app instance, dispose of it, build a new instance on the same file, and read everything back.
- **Constraint tests:** use plain connections to try the forbidden writes directly (a published or unpublished article without a pointer; a pointer to another article's snapshot; deleting the pointed-to snapshot). Each must be rejected.
- **Frontend:** no automated tests for now. The lifecycle rules are what this project is judged on, and they are all enforced and tested in the backend, so that is where the testing effort goes. Scenarios marked (FE) in the specs are checked by hand in the browser, as each frontend task's verification step and again in the final walkthrough (task 12.2).

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

- **Layers.** Data flows one way, and each layer has one job:

  ```
  services/      API calls only. Typed functions over fetch; a non-2xx
     |           response throws ApiError {code, title, message}.
     v           No state, no Vue.
  composables/   Business logic and state. Hold refs, computed values,
     |           and actions (save, publish, restore, ...). Decide what
     v           a 409 or 503 means for the UI. The only callers of services.
  views/         Pages. Call one composable and pass its state and actions
     |           to components. No API calls, no business rules.
     v
  components/    Presentational. Props in, events out. No API calls,
                 no business rules, no composables that fetch data.
  ```

  The rule of thumb: if logic would need a test, it belongs in a composable. Views and components only render and forward events.
- **Composables.**

  | Composable | Owns |
  |---|---|
  | `useArticleList` | The writer's article list and its loading and error state |
  | `useArticleEditor(id?)` | Everything on the editor page: `saved`, `form`, `isDirty`, versions, the conflict state, the busy flag (below), the pending confirmation (below), and every action: save (create or update), publish, unpublish, restore, delete, reload latest |
  | `usePublicArticles` | The public list and the public article by slug |

  Restore and delete live in `useArticleEditor`, not in a separate history composable, so they share the editor's busy flag and refresh the same state.
- **Editor state.** There is no Pinia: all editor state belongs to one page and one composable instance. The editor keeps two copies of the draft:
  - `saved`: the last draft returned by the API, plus its `draftVersion`;
  - `form`: what is in the inputs.

  `isDirty` is a computed comparison of `form` against `saved` on title, body, and tags. So typing a change and then reverting it clears the dirty state. After a successful save, both `form` and `saved` are replaced with the article the API returns, so normalized tags (for example "API" stored as "api") do not leave the editor looking dirty.
- **One action at a time (busy flag).** While any write is in flight, the editor must not start another one, for example a restore while a save is running.
  - **What it is.** A page-level flag: `useArticleEditor` holds `pendingAction: 'save' | 'publish' | 'unpublish' | 'restore' | 'delete' | 'reload' | null` and a computed `isBusy`. There is one composable instance per editor page, so the flag belongs to that page; there is no global store.
  - **When it is set.** An action sets `pendingAction` just before its request is sent and clears it in a `finally` block, so a failed request never leaves the page stuck. For actions that need confirmation (publish, restore over unsaved edits, delete, reload latest), the flag is set only **after** the writer confirms. Opening the modal does not lock anything, and cancelling it changes nothing.
  - **What the UI does.** While `isBusy`, every action control is disabled: Save, Publish, Unpublish, Reload latest, and Restore and Delete in the history panel. The active one shows a progress label such as "Publishing…".
  - **Protection relies on the disabled state.** There is no separate guard function: setting the flag disables the buttons on Vue's next render, which happens before the browser handles another click. The backend's draft-version check (409) remains the safety net if anything slips through.
  - **Why a flag and not a debounce.** A debounce delays or merges calls based on time, which suits typing, such as search boxes. Here the requirement is "nothing else until this request finishes", however long it takes. A flag expresses exactly that, with no timing values to tune.
- **Confirmation modal.** `ConfirmModal` is one reusable, presentational component, driven entirely by props and events:

  | Prop | Purpose |
  |---|---|
  | `open` | Whether the modal is shown |
  | `title`, `message` | The question and its explanation |
  | `confirmLabel`, `cancelLabel` | Button text (defaults "Confirm" and "Cancel") |
  | `tone` | `default` or `danger` (danger for delete) |

  It emits `confirm` and `cancel`. Escape and a backdrop click emit `cancel`. Because everything comes from props, the same component serves every confirmation and updates whenever its props change.

  `useArticleEditor` owns which confirmation is pending: `requestPublish()`, `requestDelete(versionId)`, and the others fill a `confirmation` object (`open`, `title`, `message`, `confirmLabel`, `tone`). `confirmPending()` closes it and runs the matching action, which is when the busy flag is set; `cancelPending()` just closes it. The editor view renders one `<ConfirmModal v-bind="confirmation" @confirm="confirmPending" @cancel="cancelPending" />`.

  Publish always asks first: "Publish this draft? Readers will see it immediately." Restore over unsaved edits, delete a snapshot, and reload latest after a conflict use the same component with their own text, so there is one confirmation pattern, not several.
- **Save routing.** The editor has one Save action backed by two endpoints. With no article id yet (`/studio/new`), Save calls `POST /api/admin/articles`; on 201 the app takes the returned id and draft version and navigates to `/studio/articles/:id`. From then on, Save calls `PATCH /api/admin/articles/{id}/draft` with the loaded `expectedDraftVersion`. The endpoints stay separate because only create accepts a slug and checks it is unique, and only save checks the draft version.
- **Unsaved-change protection.** Publish is disabled when `isDirty` is true, with the hint "Save your changes before publishing". There is deliberately no leave-page warning; it is out of scope.
- **Conflicts.** A 409 from save, restore, or publish shows a banner, keeps `form` as it is, and offers "Reload latest". That action fetches the article and replaces both `form` and `saved`, after the writer confirms.
- **Errors.** A 503 shows the API's `title` and `message` as a page-level error and does not retry.
- **Markdown.** `lib/markdown.ts` exports one `markdown-it` instance with `html: false` and the default `validateLink`, which rejects `javascript:`, `vbscript:`, `file:`, and non-image `data:` URLs. It is used by the preview, snapshot view, and public article page through one `MarkdownView` component. The output is inserted with `v-html` only from this renderer.
- **Styling: native CSS and design tokens.** Styles are plain CSS with no preprocessor. Tokens are CSS custom properties, and component styles use native CSS nesting (`&`). The files in `styles/`:

  | File | Contents |
  |---|---|
  | `tokens.css` | Everything on `:root`: color tokens (`--color-text`, `--color-text-muted`, `--color-bg`, `--color-surface`, `--color-border`, `--color-primary`, `--color-danger`, `--color-warning`, `--color-success`, and one per article status); the spacer scale (`--space-0` to `--space-8`, on a 4px base); the type scale (`--font-size-xs` to `--font-size-3xl`, with `--line-height-*` and `--font-weight-*`); radii (`--radius-sm`, `--radius-md`); and the content width and gutter |
  | `grid.css` | A 12-column CSS grid: a `.container` with the page gutter, `.grid`, and `.col-span-1` to `.col-span-12`, with column spans adjusting at the breakpoints |
  | `typography.css` | Base element styles (body, headings, code, links) and the rendered-Markdown styles, built only from tokens |
  | `main.css` | Imports the above; imported once in `main.ts` |

  Custom properties cannot be used inside `@media` conditions, so the two breakpoint widths (`48rem` and `64rem`) are written as literal values in `grid.css`, the only place they appear, and are listed as tokens in a comment at the top of `tokens.css`.

  **The tokens-only rule.** Component and view styles use only `var(--…)` tokens. They contain:
  - no raw colors (hex, `rgb()`, named colors);
  - no raw sizes for spacing or type (`px` or `rem` literals);
  - no new custom properties (`--…` definitions).

  A new value is added to `tokens.css` first, then used. The rule is checked by a search of `src/components` and `src/views` for hex colors, `px`/`rem` literals, and `--` definitions (task 10.9). It is not enforced by a linter, to keep tooling minimal.

### 9. Invariants and edge cases

Each invariant and edge case below is also a requirement or scenario in the specs; this section collects them in one place and shows where each is enforced and tested. The README reuses both tables.

**Invariants (rules that must always hold):**

| # | Invariant | Spec requirement | Enforced by | Tests (tasks) |
|---|---|---|---|---|
| INV-1 | A snapshot never changes once created, live or not. Published content changes only by editing the draft and publishing a new snapshot. | article-publishing: Snapshots are immutable | `BEFORE UPDATE` trigger; no snapshot-edit endpoint; publish copies the saved draft | 2.4, 5.6 |
| INV-2 | Readers only ever see the live snapshot of a `published` article. They never see a draft, and see nothing at all for draft-only or unpublished articles. | public-reader: List published articles; Read a published article; Hide everything that is not published | Public queries join on the pointer, filter on `published`, and never select draft columns | 7.1, 7.2 |
| INV-3 | Status, pointer, and `published_at` always agree: a draft has neither; a published or unpublished article has both, and the pointer names one of its own snapshots. This holds after a crash and under concurrent requests. | article-publishing: Publication state is always consistent | CHECK constraint; composite FK; `BEGIN IMMEDIATE`; journal + `synchronous = FULL` (crash case rests on SQLite's guarantee, Decision 3) | 2.5, 5.4 |
| INV-4 | A publish is all or nothing: snapshot, counter, status, pointer, and `published_at` change together or not at all. | article-publishing: Publishing is atomic | One `write_txn` | 5.3 |
| INV-5 | The snapshot an article points to can never be deleted, whether the article is published or unpublished. | version-history: The pointed-to snapshot cannot be deleted | Service check plus `ON DELETE RESTRICT` | 2.5, 6.3 |
| INV-6 | Restore only copies a snapshot into the draft. It never publishes, and never creates, changes, or deletes a snapshot. | version-history: Restore a snapshot into the draft | Restore only updates `articles` | 6.2 |
| INV-7 | A write based on an out-of-date draft (save, restore, or publish) is rejected with 409, never applied. | article-authoring: Detect stale draft writes; article-publishing: Publishing requires a current draft version; version-history: Restore requires a current draft version | Compare-and-set on `draft_version` | 4.3, 5.2, 6.2 |
| INV-8 | Unpublish changes only the status. Every snapshot, the pointer, and `published_at` survive it. | article-publishing: Unpublish is a status change only | Status-only UPDATE; CHECK requires the pointer | 5.5 |
| INV-9 | `published_at` is set on the first publish and never changes afterwards. | article-publishing: Republishing preserves the first publication time | `COALESCE(published_at, now)` | 5.2, 5.5 |
| INV-10 | Snapshot numbers per article only go up and are never reused, even after deletions. | article-publishing: Snapshot numbers increase and are never reused | Monotonic counter; `UNIQUE(article_id, version_number)` | 5.4, 6.4 |
| INV-11 | A slug is unique and never changes after the article is created. | article-authoring: Slugs are unique; Slugs are fixed after creation | `UNIQUE(slug)`; draft saves reject `slug` | 4.1, 4.3 |
| INV-12 | A failed write leaves no partial change behind. | api-errors: Failed writes leave no partial changes | `write_txn` rolls back on any exception | 2.3, 5.3 |

**Edge cases:**

| # | Situation | Expected result | Tests (tasks) |
|---|---|---|---|
| EC-01 | Two writers load the same draft; both save | First succeeds; second gets 409 "Draft conflict"; first writer's content kept | 4.3 |
| EC-02 | Publish with an out-of-date draft version | 409; no snapshot created | 5.2 |
| EC-03 | Publish fails after the snapshot is written | Full rollback: no snapshot; status, pointer, `published_at`, counter unchanged | 5.3 |
| EC-04 | Two publishes of the same article at once | Both succeed one after the other, with consecutive numbers | 5.4 |
| EC-05 | Direct SQL update of a snapshot, live or historical | Rejected by the database; snapshot unchanged | 2.4, 5.6 |
| EC-06 | Draft edited and saved after publishing | Public content unchanged | 7.2 |
| EC-07 | Delete the live snapshot | 409; snapshot kept | 6.3 |
| EC-08 | Delete a historical snapshot | 204; only that snapshot removed | 6.3 |
| EC-09 | Unpublish a published article | Public returns 404; every snapshot kept | 5.5, 7.2 |
| EC-10 | Unpublish, then delete the snapshot the article still points to | 409; snapshot kept | 6.3 |
| EC-11 | Restore an older snapshot | Draft equals that snapshot; history unchanged; public content unchanged | 6.2 |
| EC-12 | Restore with an out-of-date draft version | 409; draft unchanged | 6.2 |
| EC-13 | Delete the highest snapshot (not pointed to), then publish | New number is one above the counter; the deleted number is not reused | 6.4 |
| EC-14 | Public read of a draft-only article | 404 | 7.2 |
| EC-15 | Public read of an unpublished article | 404 | 7.2 |
| EC-16 | Create with a slug that is already taken | 409; nothing created | 4.1 |
| EC-17 | View, restore, or delete a snapshot under the wrong article | 404 | 6.1, 6.2, 6.3 |
| EC-18 | Invalid request body or malformed id | Framework-default 422 | 3.3 |
| EC-19 | Write lock not available within the busy timeout | 503 "Service temporarily unavailable"; no partial change | 8.1 |
| EC-20 | Unpublish an article that was never published | 409 | 5.5 |
| EC-21 | Publish again after unpublishing | New snapshot with the next number; `published_at` unchanged | 5.5 |
| EC-22 | Publish twice with no draft changes | Two snapshots with identical content | 5.2 |
| EC-23 | Known application error | Flat `{code, title, message?}` body | 3.1 |
| EC-24 | Unexpected exception | Generic 500; details logged, not returned | 3.2 |
| EC-25 | (FE) Preview unsaved Markdown | Renders in the browser; no request sent | 10.3 |
| EC-26 | (FE) View a historical snapshot | Shows that snapshot's content, not the draft | 10.8 |
| EC-27 | A write fails partway for any reason | Rolled back before the error response; lock released | 2.3 |
| EC-28 | Point an article at another article's snapshot (direct SQL) | Rejected by the database | 2.5 |
| EC-29 | Application restarts | Every article, draft, snapshot, and state unchanged | 8.2 |
| EC-30 | Unpublish an already unpublished article | 409 | 5.5 |
| EC-31 | Republish moves the pointer, then delete the previously pointed-to snapshot | 204; allowed now that it is no longer pointed to | 6.3 |
| EC-32 | Restore an old snapshot, then publish | A new snapshot (next number) with the old content; the old snapshot is not reused or re-pointed | 6.2 |
| EC-33 | Publish and unpublish of the same article at once | Run one after the other; final state consistent | 5.4 |
| EC-34 | Database cannot be opened | Every endpoint returns 503 "Database unavailable"; recovers without restart | 3.4, 4.2, 7.1 |
| EC-35 | Process stops mid-publish | After restart the article is as before the publish (SQLite's guarantee; no test of our own) | — |
| EC-36 | Draft save that includes a slug | 422; slug unchanged | 4.3 |
| EC-37 | Public read of an unknown slug | 404, identical to EC-14 and EC-15 | 7.2 |
| EC-38 | Tags with mixed case, spaces, or duplicates | Stored trimmed, lowercased, de-duplicated | 3.3 |
| EC-39 | (FE) Editor has unsaved changes | Publish disabled with "Save your changes before publishing" | 10.4 |
| EC-40 | (FE) Writer clicks Restore (or anything else) while a save or publish is in flight | Not available; only the in-flight request is sent | 10.6 |
| EC-41 | (FE) Writer cancels the publish confirmation | No request is sent; nothing changes | 10.5 |

## Risks / Trade-offs

- [Unpublish keeps the pointer, so the last published snapshot can't be deleted while unpublished] → Documented in the README with the workaround: publish again (unchanged content is fine), which moves the pointer, then delete the old snapshot.
- [Publish and unpublish have no concurrency counter of their own; two writers' publish and unpublish decisions can override each other] → Publish does carry `expectedDraftVersion`, so nobody can publish content they haven't seen. Unpublish only acts on a `published` article and returns 409 otherwise, so a repeated unpublish fails visibly rather than silently. A separate state counter is listed as future work.
- [SQLite allows one writer at a time] → Fine for an internal tool with a handful of writers. Writes are short, and the busy timeout turns long waits into a 503. Postgres with row locks is the path for higher write volume.
- [Error mapping matches SQLite error message text] → The messages are stable across SQLite versions. The mapping is covered by tests for both the slug and the FK cases, so a change would fail the tests rather than silently returning 500.
- [No migration handler yet; `migrations/` holds only the initial schema] → Fine for a first version with no deployed data. Changing the schema of an existing local database means deleting the file. The next step is a runner that applies numbered files and tracks them in `PRAGMA user_version`.
- [The app starts even when the database cannot be opened] → Deliberate, so clients get a clear 503 instead of "connection refused", and the app recovers without a restart. The failure is logged at startup and on each failed request, so it is not silent.
- [Publishing unchanged content creates duplicate snapshots] → Intended for now. Idempotent publish is a known stretch goal and is out of scope.
- [The rollback test recognises the UPDATE by its SQL text] → If the statement is reworded, the test fails loudly, because the publish then succeeds and its assertions break. So it cannot pass silently.
- [No automated frontend or end-to-end tests] → Frontend behavior, including the publish modal, the busy flag, and Markdown safety, is checked by hand. Nothing tests the full path from browser to database automatically, so a UI regression, or a mismatch between the frontend and the API, would only be caught by the manual walkthrough (task 12.2). This is accepted because the lifecycle invariants are enforced and tested in the backend, so a UI bug cannot corrupt data. Next steps, in order: Vitest tests for the composables (where the logic lives, so no page rendering is needed), then a few Playwright end-to-end tests for create, publish, restore, and unpublish.
- [The tokens-only rule is checked by a search, not a linter] → Cheap and enough for one developer. A Stylelint config with `color-no-hex` and unit restrictions would enforce it automatically.
- [Native CSS nesting needs a current browser (Chrome 120+, Safari 17.2+, Firefox 117+)] → Fine for an internal tool and a reviewer's machine. Older browsers would need a build-time step such as Lightning CSS, which Vite supports.
- [The busy flag relies on buttons disabling before a second click, with no separate guard] → Vue re-renders before the browser handles the next click, so this holds in practice. If it ever did not, the backend's draft-version 409 stops a duplicate save or publish from overwriting anything.
- [Only a single Uvicorn worker is tested] → Correctness comes from SQLite locking, not process memory, so more workers stay correct. This is documented but not tested.
- [Only the latest saved draft is stored; draft saves have no history] → Saving increments `draft_version` for concurrency but keeps no earlier draft. Published snapshots are the version history. An overwritten unpublished draft cannot be recovered, which is acceptable because the brief's safety net is about publishes. A "save as version" feature would be the extension.
- [No overall request timeout] → The only time limit is SQLite's busy timeout. It bounds how long a write waits for the lock (5 s by default), not how long a request takes. There is no HTTP deadline, no write queue, and no automatic retry. A request that cannot get the lock returns 503 without a `Retry-After` header, and the UI shows the error without retrying; the writer can simply try the action again. Writes are a few short statements, so a server-side deadline would add complexity without a real case to handle.
