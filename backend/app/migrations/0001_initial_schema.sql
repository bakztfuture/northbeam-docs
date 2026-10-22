-- Initial schema. Applied on every startup by init_db(); every statement uses
-- IF NOT EXISTS, so re-running it against an existing database changes nothing.
-- This is not a migration runner: nothing records which files have run.

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
    -- The pointer must name a snapshot of this same article, and that snapshot
    -- cannot be deleted while it is pointed to.
    FOREIGN KEY (id, current_published_version_id)
        REFERENCES article_versions (article_id, id) ON DELETE RESTRICT,
    -- Status, pointer, and published_at only exist in legal combinations.
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

-- Snapshots are immutable: any UPDATE, on any row, is rejected.
CREATE TRIGGER IF NOT EXISTS prevent_article_version_update
BEFORE UPDATE ON article_versions
BEGIN
    SELECT RAISE(ABORT, 'Published snapshots are immutable');
END;
