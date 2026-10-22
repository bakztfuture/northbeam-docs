# Spec Delta

## Purpose

Turns an article's saved draft into immutable, numbered, publicly readable snapshots, and lets the writer take an article offline again, with the guarantee that publication state is always consistent, even after a failure or under concurrent requests.

## ADDED Requirements

### Requirement: Publish the saved draft
Publishing SHALL create a new snapshot containing the article's saved draft title, body, and tags, set the article's status to `published`, and point the article at that new snapshot. Publishing SHALL use the saved draft, never unsaved editor content, and SHALL NOT change the draft.

#### Scenario: First publish
- **WHEN** the writer publishes a draft-only article with its current draft version
- **THEN** the API returns 201 with snapshot version number 1
- **AND** the article's status is `published` and it points at that snapshot
- **AND** the snapshot's title, body, and tags equal the saved draft

#### Scenario: Draft is untouched by publishing
- **WHEN** an article is published
- **THEN** its draft fields and draft version are unchanged

### Requirement: Publishing requires a current draft version
Every publish request SHALL include the draft version the writer last loaded. If it does not match the article's current draft version, the publish SHALL be rejected with 409 and nothing SHALL change.

#### Scenario: Publish with a stale draft version
- **WHEN** another writer has saved the draft since this writer loaded it, and this writer publishes with the older version
- **THEN** the API returns 409
- **AND** no snapshot is created and the article's status, live snapshot, and `published_at` are unchanged

#### Scenario: Publish a missing article
- **WHEN** the writer publishes an article id that does not exist
- **THEN** the API returns 404

### Requirement: Snapshot numbers increase and are never reused
Each publish SHALL give its snapshot the next number for that article, one higher than the highest number ever assigned to it. Numbers SHALL be unique per article and SHALL NOT be reused, even after snapshots are deleted.

#### Scenario: Numbers increase with each publish
- **WHEN** an article is published three times
- **THEN** its snapshots are numbered 1, 2, and 3

#### Scenario: Deleted numbers are not reused
- **WHEN** an article has snapshots 1, 2, and 3, snapshot 3 is deleted after the pointer has moved elsewhere, and the article is published again
- **THEN** the new snapshot is numbered 4

#### Scenario: Concurrent publishes get distinct numbers
- **WHEN** two publish requests for the same article run at the same time with the same current draft version
- **THEN** the publishes run one after the other and both succeed, with consecutive snapshot numbers
- **AND** no two snapshots of the article share a number and the article points at the higher-numbered one

### Requirement: Republishing preserves the first publication time
`published_at` SHALL be set to the time of the article's first successful publish and SHALL keep that value on every later publish, including a publish after unpublishing. Every republish SHALL create a new snapshot and SHALL NOT change earlier snapshots.

#### Scenario: Republish keeps published_at
- **WHEN** a published article is edited and published again
- **THEN** a new snapshot with the next number is created and becomes live
- **AND** `published_at` is unchanged and earlier snapshots are unchanged

#### Scenario: Publishing unchanged content creates a new snapshot
- **WHEN** the writer publishes an article twice without changing the draft in between
- **THEN** two separate snapshots exist with identical content and consecutive numbers

### Requirement: Publishing is atomic
Creating the snapshot, advancing the snapshot counter, setting status, moving the live pointer, and setting `published_at` SHALL succeed or fail together. If a publish fails at any point, including the process stopping mid-publish, the stored state SHALL be exactly as it was before the request.

#### Scenario: Failure after the snapshot is written
- **WHEN** a publish fails after its snapshot has been written but before the article's publication state is updated
- **THEN** the request fails and no new snapshot exists
- **AND** the article's status, live snapshot, `published_at`, snapshot counter, and draft are all unchanged
- **AND** a later successful publish receives the next expected snapshot number

#### Scenario: Process stops mid-publish
- **WHEN** the application process stops abruptly after a publish's snapshot has been written but before it commits
- **THEN** after a restart no new snapshot exists and the article's status, live snapshot, and `published_at` are as they were before the publish

### Requirement: Unpublish is a status change only
Unpublishing SHALL change a `published` article's status to `unpublished` and nothing else. The live snapshot reference, `published_at`, the draft, and every snapshot SHALL be kept. Unpublishing an article that is not `published` SHALL return 409.

#### Scenario: Unpublish a published article
- **WHEN** the writer unpublishes a published article
- **THEN** the API returns 200 with status `unpublished`
- **AND** the article still references its last published snapshot and keeps its `published_at`
- **AND** every snapshot still exists

#### Scenario: Unpublished article is hidden publicly
- **WHEN** an article has been unpublished
- **THEN** public reads of it return 404

#### Scenario: Unpublish a draft-only article
- **WHEN** the writer unpublishes an article that has never been published
- **THEN** the API returns 409 and nothing changes

#### Scenario: Unpublish twice
- **WHEN** the writer unpublishes an article that is already `unpublished`
- **THEN** the API returns 409 and nothing changes

#### Scenario: Republish after unpublish
- **WHEN** an unpublished article is published again
- **THEN** a new snapshot with the next number is created and becomes live
- **AND** the article's status is `published` and its `published_at` is unchanged

### Requirement: Publication state is always consistent
The stored article SHALL only ever be in one of these states, and the database SHALL reject any write that would produce another: `draft` with no live snapshot and no `published_at`; `published` or `unpublished` with a live snapshot and a `published_at`. The live snapshot SHALL belong to the same article.

#### Scenario: Inconsistent state is rejected by the database
- **WHEN** a write outside the API tries to set an article to `published` with no live snapshot
- **THEN** the database rejects the write

#### Scenario: Publish and unpublish at the same time
- **WHEN** a publish and an unpublish for the same published article run at the same time
- **THEN** they run one after the other and both outcomes are legal states
- **AND** the final status, live snapshot, and `published_at` are consistent with each other

#### Scenario: Pointer to another article's snapshot is rejected
- **WHEN** a write outside the API tries to point an article at a snapshot that belongs to a different article
- **THEN** the database rejects the write

### Requirement: Snapshots are immutable
Once created, a snapshot's content and metadata SHALL never change. The database itself SHALL reject any modification of any snapshot, live or historical, including modifications made outside the API. The API SHALL NOT offer any way to edit a snapshot. Published content SHALL change only by editing the draft and publishing it as a new snapshot.

#### Scenario: Direct modification of the live snapshot is rejected
- **WHEN** a direct database update is attempted on an article's live snapshot
- **THEN** the database rejects it and the snapshot and the public content are unchanged

#### Scenario: Direct modification of a historical snapshot is rejected
- **WHEN** a direct database update is attempted on a snapshot that is not live
- **THEN** the database rejects it and the snapshot is unchanged

### Requirement: Data survives restarts
Articles, drafts, snapshots, and publication state SHALL be stored durably and SHALL be unchanged after the application is stopped and started again.

#### Scenario: Restart keeps everything
- **WHEN** articles have been created, edited, and published, and the application restarts
- **THEN** every article, draft, snapshot, and publication state is as it was before the restart
