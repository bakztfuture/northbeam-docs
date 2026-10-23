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
    errors.py            AppError and one subclass per known error, handlers
    models.py            Pydantic request/response models
    repositories/
      database.py        core DB wrappers: connect(), get_db dependency,
                         write_txn() (maps expected sqlite errors), init_db()
      queries.py         query helpers: fetch_one(), fetch_all(), insert(),
                         execute() (returns the row count)
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
Makefile                 setup, dev, test, lint, format
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
               - queries.py: small helpers the query modules use to run SQL;
                 values are always bound as parameters.
               - articles.py: one function per query (e.g. insert_version,
                 update_draft_if_version, set_published, delete_version).
               Query functions in articles.py take a connection and return
               rows or counts; they never open transactions and never raise
               HTTP errors.
```

`database.py` is the one place in the repositories layer that raises application errors. `get_db` raises `DatabaseUnavailableError` when the database cannot be opened (Decision 3), and `write_txn` turns expected SQLite failures into their `AppError` subclasses (Decision 6).

Keeping transactions in services, not repositories, means one service call can combine several repository functions inside one `write_txn`. Publish is the main case: it needs an INSERT and an UPDATE that must succeed or fail together.

`make setup` creates `backend/.venv` with `python3 -m venv` and installs the backend, then runs `npm install` in `frontend/`. `make test` runs the backend test suite (`pytest`), which is the single command for the lifecycle tests. `make dev` starts Uvicorn on port 8000 and Vite on port 5173 with a dev proxy from `/api` to the backend.

`make lint` checks both apps without changing anything and fails on any problem: Ruff (lint and format check) for the backend, ESLint and a Prettier check for the frontend. `make format` applies the same tools' fixes. Ruff is one fast tool for both jobs in Python. ESLint with `eslint-plugin-vue` and Prettier are the standard pair for Vue 3 single-file components, and `@vue/eslint-config-prettier` keeps them from disagreeing.

*Alternatives:*
- `uv` is faster and nicer but adds a prerequisite a reviewer may not have; plain `venv` + `pip` needs only Python 3.12+.
- Biome instead of ESLint + Prettier: one fast tool, but its support for Vue single-file components is still partial.
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

*Rule: the pointer is the only source of truth for what is live.* Today the pointer always names the highest-numbered snapshot, because only publish moves it (to the snapshot it just created) and the pointed-to snapshot cannot be deleted. But that is a consequence of the current operations, not a rule, and while an article is unpublished its highest snapshot is not live at all. So no query ever infers "live" from `MAX(version_number)` or from snapshot creation time, and later features (for example pointing an article back at an older snapshot) stay correct. Public reads join on `current_published_version_id` and filter on `status = 'published'`. The `isCurrent` flag in the history list compares each snapshot's id with the pointer.

*Alternatives:*
- Clearing the pointer on unpublish, which makes every snapshot deletable afterwards. Rejected because it loses the record of what was last live and allows deleting the last published snapshot, which the brief requires to be preserved.
- Computing the next number as `MAX(version_number) + 1`. It gives the same result today, because the highest snapshot is always the pointed-to one and cannot be deleted. Rejected because that guarantee would then rest on the delete rule: any later change that lets the highest snapshot be deleted would silently start reusing numbers. A stored counter keeps "never reused" true on its own.
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
                             # on any exception: ROLLBACK, then raise the
                             # mapped AppError (Decision 6) or re-raise
```

  Every write operation (create, save, publish, unpublish, restore, delete) runs inside exactly one `write_txn`. Reads run without a transaction, since each read endpoint's queries do not need a shared snapshot of the data.
- **Why `BEGIN IMMEDIATE`:** taking the write lock at `BEGIN` rather than at the first write means the read-then-write sequence (check the draft version, then insert) cannot be interleaved with another writer. It also means lock waits happen at one predictable point, which the busy timeout governs.
- **Crash safety.** SQLite's journal guarantees that a transaction that never committed is not visible after a restart, so a crash in the middle of a publish leaves the article exactly as it was before the publish. With `synchronous = FULL`, a transaction that did commit is still there after the restart. Together with the CHECK constraint, this rules out a stored state where the status and the pointer disagree.
- **Configuration.** `busy_timeout` comes from `Settings` (default 5000 ms, env `DOCS_DB_BUSY_TIMEOUT_MS`), so tests can use about 100 ms. The database path is also configurable (`DOCS_DB_PATH`, default `backend/data/docs.sqlite3`). The parent directory is created if it is missing.

**Schema setup (not a migration handler).** `backend/app/migrations/` holds a single file, `0001_initial_schema.sql`. On startup, `init_db(conn)` sets WAL mode and runs that file in one transaction. Because every statement uses `IF NOT EXISTS`, running it against an existing database changes nothing.

This is deliberately **not** a migration handler: nothing records which files have run, and only the initial file is applied. The folder exists so the schema lives in its own file and there is an obvious home for future changes. Until a runner exists, changing the schema of an existing local database means deleting the database file and letting startup recreate it. The natural next step is a small runner that applies numbered files in order and tracks progress in `PRAGMA user_version`.

**Database unavailable.** If the database cannot be opened, every endpoint must fail the same clear way instead of each one failing differently:

- **At startup**, FastAPI's `lifespan` handler calls `init_db()`. If that fails, for example because the path is unreadable or the file is not a database, the error is logged and `app.state.db_ready` stays `False`. The app still starts, so clients get a clear error response rather than "connection refused".
- **On every request**, `get_db` is the single gate. If `db_ready` is `False`, it first retries `init_db()`. Then it opens the connection. If either step raises `sqlite3.Error` or `OSError`, it raises `DatabaseUnavailableError`. The real error and the path go to the log, never into the response.
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

**Naming.** Each endpoint has one verb + noun name, used for its route function and, when it takes a body, its request model (`restore_snapshot`, `RestoreSnapshotRequest`). Request models end in `Request`. Response models are named for the thing they return (`AdminArticle`, `Snapshot`), because several endpoints return the same thing; a row in a list is a `…ListItem`. Paths and model names say "snapshot"; the fields `versionNumber` and `currentPublishedVersionId` keep the database's column names.

**Admin endpoints** (`/api/admin`):

| Method | Path | Route function | Request | Success | Errors |
|---|---|---|---|---|---|
| POST | `/articles` | `create_article` | `CreateArticleRequest` (`title, slug, body, tags`) | 201 `AdminArticle` | 409 slug taken; 422 invalid body; 500; 503 "Database unavailable"; 503 "Service temporarily unavailable" |
| GET | `/articles` | `list_articles` | | 200 `list[ArticleListItem]`, newest `updatedAt` first | 500; 503 "Database unavailable" |
| GET | `/articles/{articleId}` | `get_article` | | 200 `AdminArticle` | 404 article; 422 malformed id; 500; 503 "Database unavailable" |
| PATCH | `/articles/{articleId}/draft` | `save_draft` | `SaveDraftRequest` (`title, body, tags, expectedDraftVersion`) | 200 `AdminArticle` | 404 article; 409 stale draft version; 422 invalid body, unknown field such as `slug`, or malformed id; 500; 503 "Database unavailable"; 503 "Service temporarily unavailable" |
| POST | `/articles/{articleId}/publish` | `publish_article` | `PublishArticleRequest` (`expectedDraftVersion`) | 201 `PublishedArticle` | 404 article; 409 stale draft version; 422 invalid body or malformed id; 500; 503 "Database unavailable"; 503 "Service temporarily unavailable" |
| POST | `/articles/{articleId}/unpublish` | `unpublish_article` | | 200 `AdminArticle` | 404 article; 409 not `published`; 422 malformed id; 500; 503 "Database unavailable"; 503 "Service temporarily unavailable" |
| GET | `/articles/{articleId}/snapshots` | `list_snapshots` | | 200 `list[SnapshotListItem]`, newest first | 404 article; 422 malformed id; 500; 503 "Database unavailable" |
| GET | `/articles/{articleId}/snapshots/{snapshotId}` | `get_snapshot` | | 200 `Snapshot` | 404 article, snapshot, or snapshot of another article; 422 malformed id; 500; 503 "Database unavailable" |
| POST | `/articles/{articleId}/snapshots/{snapshotId}/restore` | `restore_snapshot` | `RestoreSnapshotRequest` (`expectedDraftVersion`) | 200 `AdminArticle` | 404 article or snapshot; 409 stale draft version; 422 invalid body or malformed id; 500; 503 "Database unavailable"; 503 "Service temporarily unavailable" |
| DELETE | `/articles/{articleId}/snapshots/{snapshotId}` | `delete_snapshot` | | 204, no body | 404 article or snapshot; 409 snapshot the article points to; 422 malformed id; 500; 503 "Database unavailable"; 503 "Service temporarily unavailable" |

**Public endpoints** (`/api/public`) and the health check:

| Method | Path | Route function | Success | Errors |
|---|---|---|---|---|
| GET | `/api/public/articles` | `list_public_articles` | 200 `list[PublicArticleListItem]`, newest `publishedAt` first | 500; 503 "Database unavailable" |
| GET | `/api/public/articles/{slug}` | `get_public_article` | 200 `PublicArticle` | 404 draft-only, unpublished, or unknown slug; 500; 503 "Database unavailable" |
| GET | `/api/health` | `health` | 200 `HealthStatus` | 500; 503 "Database unavailable" |

**Response shapes.** Every route declares its response model as `response_model`, so only the listed fields are ever sent. Ids are UUID strings; timestamps are UTC ISO 8601 with milliseconds (Decision 2).

| Shape | Fields |
|---|---|
| `AdminArticle` | `id, slug, status, draft {title, body, tags}, draftVersion, currentPublishedVersionId` (null until the first publish), `publishedAt` (null until the first publish), `createdAt, updatedAt` |
| `ArticleListItem` | `id, slug, title` (the draft title), `status, updatedAt` |
| `Snapshot` | `id, versionNumber, title, body, tags, createdAt, isCurrent` (true for the snapshot the article points to) |
| `SnapshotListItem` | `id, versionNumber, title, createdAt, isCurrent` (true for the snapshot the article points to) |
| `PublishedArticle` | `article` (`AdminArticle`), `snapshot` (the new `Snapshot`) |
| `PublicArticle` | `slug, title, body, tags, publishedAt` (no draft fields) |
| `PublicArticleListItem` | `slug, title, tags, publishedAt` (no draft fields) |
| `HealthStatus` | `status` (always `"ok"`) |

The shared errors listed in every applicable row above:
- **Every endpoint** can return **503 "Database unavailable"** when the database cannot be opened (Decision 3), and **500** for unexpected errors.
- **Write endpoints** (POST, PATCH, DELETE) can also return **503 "Service temporarily unavailable"** when the write lock is not available within the busy timeout. Reads never wait for the lock in WAL mode.
- The public slug is not format-validated, so a malformed slug is simply an unknown slug: 404, never 422.

Notes:
- **The public endpoints** join `articles` to `article_versions` on the pointer, filter on `status = 'published'`, and select only snapshot columns plus `slug` and `published_at`. The draft columns are never selected, so they cannot leak.
- **Health check.** `GET /api/health` runs `SELECT 1` through `get_db`. It returns 200 `{"status": "ok"}` (`HealthStatus`) when the database can be opened and 503 "Database unavailable" otherwise. It appears in the public table for completeness but is not one of the 12 article endpoints, and it reads no article data.
- **Draft saves reject unknown fields** (`extra="forbid"`), so a stray `slug` returns 422 rather than being silently ignored.

### 6. Validation and errors

**Pydantic models** enforce the input rules from the `article-authoring` spec:

- slug: `^[a-z0-9]+(-[a-z0-9]+)*$`, 1 to 100 characters;
- title: stripped, 1 to 200 characters;
- body: at least one non-whitespace character, at most 50,000 characters;
- tags: each one stripped, lowercased, non-empty, and at most 100 characters; at most 20 tags; duplicates removed while keeping first-seen order;
- `expectedDraftVersion`: `int >= 1`.

FastAPI's default 422 handler is left unchanged.

**Known errors.** `AppError` is the base class. Each known error is a subclass that fixes its `code` (the HTTP status), its `title`, and usually a default `message`. A raise site may pass a different message. All of them live in `errors.py`, so each title is written once. A single handler renders any of them as `{"code", "title", "message"?}`, leaving out `message` when it is `None`.

| Subclass | Code | Title | Raised by |
|---|---|---|---|
| `ArticleNotFoundError` | 404 | "Article not found" | services, for an unknown article id or public slug |
| `SnapshotNotFoundError` | 404 | "Snapshot not found" | history services, for a missing snapshot or one of another article |
| `DraftConflictError` | 409 | "Draft conflict" | save, publish, and restore, for a stale draft version |
| `SlugTakenError` | 409 | "Slug already exists" | create, and the SQLite mapping |
| `ArticleNotPublishedError` | 409 | "Article is not published" | unpublish |
| `SnapshotInUseError` | 409 | "Snapshot is in use" | snapshot delete, and the SQLite mapping |
| `DatabaseBusyError` | 503 | "Service temporarily unavailable" | the SQLite mapping |
| `DatabaseUnavailableError` | 503 | "Database unavailable" | `get_db` |

**SQLite error mapping** is done in `write_txn`, after the rollback. Every write runs inside it, and every mapped failure can only come from a write. Routes and services have no try/except blocks. An unmatched SQLite error is re-raised and becomes the generic 500:

| sqlite3 error | Message starts with | Raised as |
|---|---|---|
| `IntegrityError` | `UNIQUE constraint failed: articles.slug` | `SlugTakenError` (409) |
| `IntegrityError` | `FOREIGN KEY constraint failed` (any statement) | `SnapshotInUseError` (409) |
| `OperationalError` | `database is locked` or `database is busy` | `DatabaseBusyError` (503), no `Retry-After` |
| anything else, including CHECK and trigger aborts | | re-raised unchanged: 500 |

CHECK and trigger failures stay 500 on purpose. The API never attempts those writes, so reaching one means there is a bug, and returning 409 would hide it.

Every foreign-key failure maps to 409 "Snapshot is in use", whichever statement caused it. SQLite's message is the same for every foreign-key failure and does not name the table or statement, so a delete of the pointed-to snapshot cannot be told apart from a buggy write that points an article at a missing or foreign snapshot. The only foreign-key failure the API can legitimately reach is that delete (Decision 4); see Risks / Trade-offs.

**Unexpected errors.** Any other exception is logged with its traceback, and the response is only `{"code": 500, "title": "Internal server error"}`.

**Rollback before the response.** `write_txn` always rolls back before an exception leaves it, so by the time any handler runs, the transaction is already closed and the lock released.

*Alternative considered:* one `AppError(code, title, message)` class built at each raise site. Rejected because the same titles and messages were repeated in several files.

### 7. Testing approach

pytest; each test gets its own SQLite file in `tmp_path`. A fixture builds the app with `create_app(Settings(db_path=..., busy_timeout_ms=...))` and wraps it in FastAPI's `TestClient`. Tests go through HTTP unless a test is specifically about the database, in which case it uses a plain `sqlite3` connection to the same file. They live in two folders: `tests/api/` for tests through HTTP and `tests/database/` for plain-SQL tests, with shared fixtures in `tests/conftest.py`. Direct-SQL tests are kept to snapshot immutability and the three refusals the specs say the database itself makes, which no endpoint can trigger; every other rule is tested through the endpoints a writer actually uses.

- **Direct-SQL immutability** (mandatory): publish twice through the API so the article has a live snapshot and a historical one. Then, on a plain connection, run `UPDATE article_versions SET body = 'x' ...` against each. Each one must raise `sqlite3.IntegrityError` mentioning the immutability message. Re-reading both rows and the public endpoint must show unchanged content.
- **Database refusals:** on a plain connection, setting an article to `published` with no pointer, pointing an article at another article's snapshot, and deleting the snapshot an article points to must each raise `sqlite3.IntegrityError`. These are the specs' "rejected by the database" scenarios; the API never attempts these writes, so only direct SQL can check them.
- **Publish rollback** (mandatory): uses `app.dependency_overrides[get_db]` so that the real publish route receives a test-only wrapper around a real connection. The wrapper forwards every call to SQLite, but raises when it sees the article state update statement (`UPDATE articles SET status = 'published'`). As a result, the real `BEGIN IMMEDIATE`, SELECT, and INSERT run against SQLite, and then the real `write_txn` rolls back. The test then removes the override and checks, through a fresh plain connection:
  - there is no new snapshot row;
  - status, pointer, `published_at`, the counter, and the draft are unchanged;
  - a normal publish afterwards gets the expected next number.

  No production code exists for this test; the only requirement it places on the design is Decision 3's "services get their connection from `get_db`".
- **Database unavailable:** `DOCS_DB_PATH` points at an existing directory, which SQLite cannot open as a file. The health check must return 503 "Database unavailable", and the body must not contain the path. Then the directory is removed, and the next request succeeds without restarting the app.
- **Lock exhaustion (503):** a second plain connection holds `BEGIN IMMEDIATE`, while the app runs with a busy timeout of about 100 ms. A draft save must return 503 "Service temporarily unavailable", and after the lock is released, a save must succeed.
- **Concurrent publishes:** two threads, each with its own connection, call the publish service at the same moment, synchronised with a `threading.Barrier`. Both must succeed with consecutive numbers. A second run does the same with one publish and one unpublish, and checks the final row satisfies the status/pointer/`published_at` rules.
- **Golden-path lifecycle test:** one test walks a single article through its whole life through the HTTP API, and checks the public view, the history, the pointer, and `published_at` after every step:

  | Step | Expect |
  |---|---|
  | Create the article | Public read is 404; history is empty |
  | Save the draft twice | Draft version goes 1, 2, 3; public read still 404; no snapshots |
  | Publish (v1) | Public read returns v1's content; `published_at` set; pointer names v1 |
  | Save a new draft | Public read still returns v1, not the draft |
  | Publish (v2) | Public read returns v2; `published_at` unchanged |
  | Delete v1 | 204; history is v2 only; public still v2 |
  | Unpublish | Public read and public list are 404 and empty; pointer and `published_at` unchanged; v2 still in history |
  | Restore v2 into the draft | Draft equals v2; still unpublished; no snapshot created |
  | Delete v2 | 409, since it is still the pointed-to snapshot |
  | Publish (v3) | Public read returns v3; `published_at` unchanged; v3 numbered 3, not reusing 1 |
  | Delete v2 | 204, now that the pointer has moved |

  At every step it also checks `updated_at` and `draft_version`: both change on create, save, and restore, and neither changes on publish, unpublish, or delete.

  The individual tests cover each rule in isolation; this one proves they hold together in the order a writer would actually use them.
- **Restart durability:** create and publish through one app instance, dispose of it, build a new instance on the same file, and read everything back.
- **Frontend:** no automated tests for now. The lifecycle rules are what this project is judged on, and they are all enforced and tested in the backend, so that is where the testing effort goes. Scenarios marked (FE) in the specs are checked by hand in the browser, as each frontend task's verification step and again in the final walkthrough (task 6.2).

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
  | `useArticleEditor(id?)` | Everything on the editor page: `saved`, `form`, `isDirty`, the snapshot list, the conflict state, the busy flag (below), the pending confirmation (below), and every action: save (create or update), publish, unpublish, restore, delete, reload latest |
  | `usePublicArticles` | The public list and the public article by slug |

  Restore and delete live in `useArticleEditor`, not in a separate history composable, so they share the editor's busy flag and refresh the same state. After a publish or a delete, it reloads the snapshot list, so the "current" marker never points at the wrong snapshot.
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

  `useArticleEditor` owns which confirmation is pending: `requestPublish()`, `requestDelete(snapshotId)`, and the others fill a `confirmation` object (`open`, `title`, `message`, `confirmLabel`, `tone`). `confirmPending()` closes it and runs the matching action, which is when the busy flag is set; `cancelPending()` just closes it. The editor view renders one `<ConfirmModal v-bind="confirmation" @confirm="confirmPending" @cancel="cancelPending" />`.

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
  | `grid.css` | A 12-column CSS grid: a `.container` with the content width and page gutter, `.grid`, and `.col-span-1` to `.col-span-12`. No breakpoints: mobile layouts are out of scope |
  | `typography.css` | Base element styles (body, headings, code, links) and the rendered-Markdown styles, built only from tokens |
  | `main.css` | Imports the above; imported once in `main.ts` |

  **The tokens-only rule.** Component and view styles use only `var(--…)` tokens. They contain:
  - no raw colors (hex, `rgb()`, named colors);
  - no raw sizes for spacing or type (`px` or `rem` literals);
  - no new custom properties (`--…` definitions).

  A new value is added to `tokens.css` first, then used. The rule is checked by a search of `src/components` and `src/views` for hex colors, `px`/`rem` literals, and `--` definitions (task 5.6). ESLint and Prettier do not check CSS values, and Stylelint is not added, to keep tooling minimal.

### 9. Invariants and edge cases

Each invariant and edge case below is also a requirement or scenario in the specs; this section collects them in one place and shows where each is enforced and tested. The README reuses both tables.

**Terms used below.** Two separate fields describe an article's publication state, and they change at different times:

- **Status** (`draft`, `published`, `unpublished`) decides what readers can see. Publish sets it to `published`; unpublish sets it to `unpublished`.
- **The pointer** is the `current_published_version_id` field: the snapshot that was most recently published. Publish moves it to the new snapshot. Unpublish does **not** clear it. The specs call it the **published snapshot reference**.

So after an unpublish the status says readers see nothing, while the pointer still names the last published snapshot. That snapshot therefore stays protected from deletion until a later publish moves the pointer. This is a deliberate design limitation (see Decision 2 and Risks / Trade-offs).

The **live** snapshot is the one the pointer names while the status is `published`. A **historical** snapshot is any snapshot the pointer does not name.

**Invariants (rules that must always hold):**

| # | Invariant | Spec requirement | Enforced by | Tests (tasks) |
|---|---|---|---|---|
| INV-1 | A snapshot never changes once created, live or not. Published content changes only by editing the draft and publishing a new snapshot. | article-publishing: Snapshots are immutable | `BEFORE UPDATE` trigger; no snapshot-edit endpoint; publish copies the saved draft | 1.4, 2.3, 3.3 |
| INV-2 | Readers only ever see the live snapshot of a `published` article. They never see a draft, and see nothing at all for draft-only or unpublished articles. | public-reader: List published articles; Read a published article; Hide everything that is not published | Public queries join on the pointer, filter on `published`, and never select draft columns | 3.3 |
| INV-3 | Status, pointer, and `published_at` always agree: a draft has neither; a published or unpublished article has both, and the pointer names one of its own snapshots. This holds after a crash and under concurrent requests. | article-publishing: Publication state is always consistent | CHECK constraint; composite FK; `BEGIN IMMEDIATE`; journal + `synchronous = FULL` (crash case rests on SQLite's guarantee, Decision 3) | 1.4, 2.3 |
| INV-4 | A publish is all or nothing: snapshot, counter, status, pointer, and `published_at` change together or not at all. | article-publishing: Publishing is atomic | One `write_txn` | 2.3 |
| INV-5 | The snapshot an article points to can never be deleted, whether the article is published or unpublished. | version-history: The pointed-to snapshot cannot be deleted | Service check plus `ON DELETE RESTRICT` | 1.4, 3.3 |
| INV-6 | Restore only copies a snapshot into the draft. It never publishes, and never creates, changes, or deletes a snapshot. | version-history: Restore a snapshot into the draft | Restore only updates `articles` | 3.3 |
| INV-7 | A write based on an out-of-date draft (save, restore, or publish) is rejected with 409, never applied. | article-authoring: Detect stale draft writes; article-publishing: Publishing requires a current draft version; version-history: Restore requires a current draft version | Compare-and-set on `draft_version` | 2.3, 3.3 |
| INV-8 | Unpublish changes only the status. Every snapshot, the pointer, and `published_at` survive it. | article-publishing: Unpublish is a status change only | Status-only UPDATE; CHECK requires the pointer | 2.3 |
| INV-9 | `published_at` is set on the first publish and never changes afterwards. | article-publishing: Republishing preserves the first publication time | `COALESCE(published_at, now)` | 2.3, 3.3 |
| INV-10 | Snapshot numbers per article only go up and are never reused, even after deletions. | article-publishing: Snapshot numbers increase and are never reused | Monotonic counter; `UNIQUE(article_id, version_number)` | 2.3, 3.3 |
| INV-11 | A slug is unique and never changes after the article is created. | article-authoring: Slugs are unique; Slugs are fixed after creation | `UNIQUE(slug)`; draft saves reject `slug` | 2.3 |
| INV-12 | A failed write leaves no partial change behind. | api-errors: Failed writes leave no partial changes | `write_txn` rolls back on any exception | 2.3 |

**Edge cases:**

| # | Situation | Expected result | Tests (tasks) |
|---|---|---|---|
| EC-01 | Two writers load the same draft; both save | First succeeds; second gets 409 "Draft conflict"; first writer's content kept | 2.3 |
| EC-02 | Publish with an out-of-date draft version | 409; no snapshot created | 2.3 |
| EC-03 | Publish fails after the snapshot is written | Full rollback: no snapshot; status, pointer, `published_at`, counter unchanged | 2.3 |
| EC-04 | Two publishes of the same article at once | Both succeed one after the other, with consecutive numbers | 2.3 |
| EC-05 | Direct SQL update of a snapshot, live or historical | Rejected by the database; snapshot unchanged | 1.4, 2.3, 3.3 |
| EC-06 | Draft edited and saved after publishing | Public content unchanged | 3.3 |
| EC-07 | Delete the live snapshot | 409; snapshot kept | 3.3 |
| EC-08 | Delete a historical snapshot | 204; only that snapshot removed | 3.3 |
| EC-09 | Unpublish a published article | Public returns 404; every snapshot kept | 2.3, 3.3 |
| EC-10 | Status `unpublished`, pointer still on the last published snapshot: delete that snapshot | 409; snapshot kept (design limitation: the pointer is not cleared on unpublish) | 3.3 |
| EC-11 | Restore an older snapshot | Draft equals that snapshot; history unchanged; public content unchanged | 3.3 |
| EC-12 | Restore with an out-of-date draft version | 409; draft unchanged | 3.3 |
| EC-13 | Delete older snapshots, then publish | New number is one above the counter; deleted numbers are not reused | 3.3 |
| EC-14 | Public read of a draft-only article | 404 | 3.3 |
| EC-15 | Public read of an unpublished article | 404 | 3.3 |
| EC-16 | Create with a slug that is already taken | 409; nothing created | 2.3 |
| EC-17 | View, restore, or delete a snapshot under the wrong article | 404 | 3.3 |
| EC-18 | Invalid request body or malformed id | Framework-default 422 | 2.3 (request body only; a malformed id is not tested, see Risks) |
| EC-19 | Write lock not available within the busy timeout | 503 "Service temporarily unavailable"; no partial change | 3.3 |
| EC-20 | Unpublish an article that was never published | 409 | 2.3 |
| EC-21 | Publish again after unpublishing | New snapshot with the next number; `published_at` unchanged | 2.3 |
| EC-22 | Publish twice with no draft changes | Two snapshots with identical content | 2.3 |
| EC-23 | Known application error | Flat `{code, title, message?}` body | 3.3 |
| EC-24 | Unexpected exception | Generic 500; details logged, not returned | 2.3 (the rollback test) |
| EC-25 | (FE) Preview unsaved Markdown | Renders in the browser; no request sent | 5.6 |
| EC-26 | (FE) View a historical snapshot | Shows that snapshot's content, not the draft | 5.6 |
| EC-27 | A write fails partway for any reason | Rolled back before the error response; lock released | 2.3 |
| EC-28 | Point an article at another article's snapshot (direct SQL) | Rejected by the database | 1.4 |
| EC-29 | Application restarts | Every article, draft, snapshot, and state unchanged | 3.3 |
| EC-30 | Unpublish an already unpublished article | 409 | 2.3 |
| EC-31 | Republish moves the pointer, then delete the previously pointed-to snapshot | 204; allowed now that it is no longer pointed to | 3.3 |
| EC-32 | Restore an old snapshot, then publish | A new snapshot (next number) with the old content; the old snapshot is not reused or re-pointed | 3.3 |
| EC-33 | Publish and unpublish of the same article at once | Run one after the other; final state consistent | 2.3 |
| EC-34 | Database cannot be opened | Every endpoint returns 503 "Database unavailable"; recovers without restart | 1.4 |
| EC-35 | Process stops mid-publish | After restart the article is as before the publish (SQLite's guarantee; no test of our own) | — |
| EC-36 | Draft save that includes a slug | 422; slug unchanged | 2.3 |
| EC-37 | Public read of an unknown slug | 404, identical to EC-14 and EC-15 | 3.3 |
| EC-38 | Tags with mixed case, spaces, or duplicates | Stored trimmed, lowercased, de-duplicated | — |
| EC-43 | Body over 50,000 characters, or a tag over 100 characters | 422; nothing stored | — |
| EC-39 | (FE) Editor has unsaved changes | Publish disabled with "Save your changes before publishing" | 5.6 |
| EC-40 | (FE) Writer clicks Restore (or anything else) while a save or publish is in flight | Not available; only the in-flight request is sent | 5.6 |
| EC-41 | (FE) Writer cancels the publish confirmation | No request is sent; nothing changes | 5.6 |
| EC-42 | Status `unpublished`, pointer still on v3: delete a historical snapshot, v1 | 204; only v1 removed; status stays `unpublished` and the pointer stays on v3 | 3.3 |

## Risks / Trade-offs

- [Unpublish keeps the pointer, so the last published snapshot can't be deleted while unpublished] → Documented in the README with the workaround: publish again (unchanged content is fine), which moves the pointer, then delete the old snapshot.
- [Publish and unpublish have no concurrency counter of their own; two writers' publish and unpublish decisions can override each other] → Publish does carry `expectedDraftVersion`, so nobody can publish content they haven't seen. Unpublish only acts on a `published` article and returns 409 otherwise, so a repeated unpublish fails visibly rather than silently. A separate state counter is listed as future work.
- [SQLite allows one writer at a time] → Fine for an internal tool with a handful of writers. Writes are short, and the busy timeout turns long waits into a 503. Postgres with row locks is the path for higher write volume.
- [Error mapping matches SQLite error message text] → The messages are stable across SQLite versions. The slug and foreign-key mappings are not reached by an automated test (the API checks for both cases before writing), so a change in their message text would show up as a 500 rather than a failing test. The busy mapping is tested (EC-19).
- [Every foreign-key failure maps to 409 "Snapshot is in use"] → SQLite reports every foreign-key failure with the same message, so the mapping cannot tell a protected-snapshot delete from a bug that writes a bad pointer. Such a bug would return a misleading 409 instead of a 500. This is accepted because the API never writes the pointer except in the publish transaction, right after inserting that same snapshot. A precise mapping would need the delete service to catch the error itself, instead of letting `write_txn` map it.
- [No migration handler yet; `migrations/` holds only the initial schema] → Fine for a first version with no deployed data. Changing the schema of an existing local database means deleting the file. The next step is a runner that applies numbered files and tracks them in `PRAGMA user_version`.
- [The app starts even when the database cannot be opened] → Deliberate, so clients get a clear 503 instead of "connection refused", and the app recovers without a restart. The failure is logged at startup and on each failed request, so it is not silent.
- [Publishing unchanged content creates duplicate snapshots] → Intended for now. Idempotent publish is a known stretch goal and is out of scope.
- [The writer's article list is ordered newest `updatedAt` first] → The brief only fixes the order of version history. We chose most recently updated first so the articles a writer is working on come to the top. Because `updated_at` changes only when the draft changes, publishing or unpublishing does not reorder the list.
- [Saving a draft with no changes is accepted] → The API does not compare the submitted draft with the stored one, so an identical save still succeeds, increments `draft_version`, and updates `updated_at`. No data is lost, but another writer holding the old version will get a 409 they didn't strictly need. The editor could disable Save while `isDirty` is false, and the backend could skip the update when nothing changed; neither is in scope.
- [No slug collision handling, and the slug race is not tested directly] → A slug that is already taken is rejected with 409; there is no automatic suffix or suggestion. If two creates with the same slug arrive at the same moment, both can pass the application check, and the database's `UNIQUE(slug)` constraint rejects the second, which the error mapping turns into a 409 (Decision 6). The ordinary duplicate is tested (task 2.3), but no test forces a real two-request race. Acceptable with a single writer; collision handling is a known stretch goal.
- [The slug is not derived from the title] → The writer types the slug when creating the article; it is not generated from the title and does not follow later title changes. This keeps public URLs stable. Generating it from the title, with automatic suffixes on collisions, would be a later addition.
- [No audit log] → Nothing records who did what and when beyond the timestamps already stored: `created_at`, `updated_at`, `published_at`, and each snapshot's `created_at`. There is no history of unpublishes, restores, or deletions, and no record of who acted, since there are no users. Acceptable with a single trusted writer and no authentication. The next step is an `article_events` table (article, action, actor, time) written inside the same transaction as each write. With users in place, sensitive actions such as publish or restore could then notify reviewers or require explicit approval.
- [No rate limiting] → The API accepts any number of requests. Acceptable for an internal tool with no public write access; the public endpoints are read-only and cheap. Adding limits later belongs in middleware or in front of the app, for example a reverse proxy.
- [No leave-page warning for unsaved edits] → Descoped. Navigating away, closing the tab, or reloading discards unsaved editor content without asking. The main risk is already covered, since Publish is disabled while there are unsaved changes, so unsaved content can never go live by mistake.
- [No dark mode] → Out of scope. Colors are all tokens on `:root`, so a dark theme would be a second set of color tokens under `@media (prefers-color-scheme: dark)`, with no component changes.
- [Not designed for mobile] → Out of scope. The layout targets desktop and laptop screens and is not tested on phones. Because spacing, type, and layout all come from tokens and one grid, a responsive pass later means adding breakpoints in `grid.css` rather than reworking components.
- [No accessibility work] → Out of scope. The UI is not designed or tested for keyboard, screen-reader, or contrast support;
- [Some spec scenarios have no automated test] → The input limits and tag normalization are enforced by Pydantic but not tested. The unknown-article 404 is tested on read and on the snapshot list, but not on save or publish ("Saving a missing article", "Publish a missing article"), which use the same lookup. A malformed id in the path ("Malformed id") is rejected with 422 by FastAPI's `UUID` typing before any of our code runs, so it is not tested either. Testing effort goes to the paths a writer actually uses, plus direct-SQL checks for snapshot immutability and the database refusals no endpoint can trigger. Tests for these can be added if any of them changes.
- [No backend unit tests; the suite is integration tests only] → Every test goes through HTTP or a plain connection to a real SQLite file, because the lifecycle rules live in SQL, transactions, and constraints that a mock would skip. Two pieces of pure logic would still benefit from fast unit tests, and are the first ones to add:
  - Input validation in `models.py`: tag normalization, a blank tag or title or body, too many tags, and the length limits, by building the request models directly. These are the spec scenarios listed as untested above.
  - `_map_sqlite_error` in `database.py`: build each `sqlite3` error with SQLite's real message and check which `AppError` comes back, including a CHECK failure staying a 500. Only the busy mapping is reached by a test today, so this would catch a change in SQLite's message text.

  Unit tests for `services/` and `repositories/` were considered and rejected for now: the services are thin glue over the repositories, every branch that matters already runs in the HTTP tests, and a mocked repository would test call order rather than behavior.
- [The rollback test recognises the UPDATE by its SQL text] → If the statement is reworded, the test fails loudly, because the publish then succeeds and its assertions break. So it cannot pass silently.
- [No automated frontend or end-to-end tests] → Frontend behavior, including the publish modal, the busy flag, and Markdown safety, is checked by hand. Nothing tests the full path from browser to database automatically, so a UI regression, or a mismatch between the frontend and the API, would only be caught by the manual walkthrough (task 6.2). This is accepted because the lifecycle invariants are enforced and tested in the backend, so a UI bug cannot corrupt data. Next steps, in order: Vitest tests for the composables (where the logic lives, so no page rendering is needed), then a few Playwright end-to-end tests for create, publish, restore, and unpublish.
- [The tokens-only rule is checked by a search, not a linter] → Cheap and enough for one developer. A Stylelint config with `color-no-hex` and unit restrictions would enforce it automatically.
- [Native CSS nesting needs a current browser (Chrome 120+, Safari 17.2+, Firefox 117+)] → Fine for an internal tool and a reviewer's machine. Older browsers would need a build-time step such as Lightning CSS, which Vite supports.
- [The busy flag relies on buttons disabling before a second click, with no separate guard] → Vue re-renders before the browser handles the next click, so this holds in practice. If it ever did not, the backend's draft-version 409 stops a duplicate save or publish from overwriting anything.
- [Only a single Uvicorn worker is tested] → Correctness comes from SQLite locking, not process memory, so more workers stay correct. This is documented but not tested.
- [Only the latest saved draft is stored; draft saves have no history] → Saving increments `draft_version` for concurrency but keeps no earlier draft. Published snapshots are the version history. An overwritten unpublished draft cannot be recovered, which is acceptable because the brief's safety net is about publishes. A "save as version" feature would be the extension.
- [No overall request timeout] → The only time limit is SQLite's busy timeout. It bounds how long a write waits for the lock (5 s by default), not how long a request takes. There is no HTTP deadline, no write queue, and no automatic retry. A request that cannot get the lock returns 503 without a `Retry-After` header, and the UI shows the error without retrying; the writer can simply try the action again. Writes are a few short statements, so a server-side deadline would add complexity without a real case to handle.
