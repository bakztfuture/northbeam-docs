# Spec Delta

## Purpose

Gives the writer a safety net over published content: inspect every snapshot an article has, copy any of them back into the draft, and remove snapshots that are no longer needed, without ever losing the snapshot the article points to.

## ADDED Requirements

### Requirement: List an article's snapshots
The writer API SHALL list every existing snapshot of an article, newest first (descending version number), with each snapshot's id, version number, title, tags, creation time, and whether it is the snapshot the article currently points to. An unknown article SHALL return 404.

#### Scenario: Snapshots are newest first
- **WHEN** an article has snapshots 1, 2, and 3
- **THEN** the list returns them in the order 3, 2, 1

#### Scenario: The pointed-to snapshot is marked
- **WHEN** an article points at snapshot 2
- **THEN** snapshot 2 is marked as current in the list and the others are not

#### Scenario: Article with no snapshots
- **WHEN** a draft-only article's history is listed
- **THEN** the API returns 200 with an empty list

#### Scenario: Unknown article
- **WHEN** the history of an article id that does not exist is requested
- **THEN** the API returns 404

### Requirement: View one snapshot
The writer API SHALL return a single snapshot's title, Markdown body, tags, version number, and creation time. A snapshot that does not exist, or that belongs to a different article than the one in the request, SHALL return 404.

#### Scenario: View a snapshot
- **WHEN** the writer views snapshot 1 of an article whose draft has since changed
- **THEN** the API returns snapshot 1's original content, not the draft

#### Scenario: Snapshot of another article
- **WHEN** the writer requests a snapshot id under an article it does not belong to
- **THEN** the API returns 404

### Requirement: Restore a snapshot into the draft
Restoring SHALL copy a snapshot's title, body, and tags into the article's draft and increment the draft version. It SHALL NOT publish, and SHALL NOT change status, the published snapshot reference, `published_at`, or any snapshot. No snapshot SHALL be created or deleted.

#### Scenario: Restore an older snapshot
- **WHEN** a published article has snapshots 1 and 2 with 2 live, and the writer restores snapshot 1 with the current draft version
- **THEN** the API returns 200 and the draft equals snapshot 1's content with the draft version increased by one
- **AND** snapshot 2 is still live and public readers still see snapshot 2's content
- **AND** the article still has exactly snapshots 1 and 2, both unchanged

#### Scenario: Restored content goes live only on publish
- **WHEN** the writer restores snapshot 1 and then publishes
- **THEN** a new snapshot 3 with snapshot 1's content is created and becomes live

### Requirement: Restore requires a current draft version
Every restore request SHALL include the draft version the writer last loaded. If it does not match the article's current draft version, the restore SHALL be rejected with 409 and the draft SHALL be left unchanged. A missing snapshot, or one belonging to another article, SHALL return 404.

#### Scenario: Restore with a stale draft version
- **WHEN** the draft was saved by someone else after this writer loaded it, and this writer restores with the older version
- **THEN** the API returns 409 and the draft keeps the other writer's content

#### Scenario: Restore a missing snapshot
- **WHEN** the writer restores a snapshot id that does not exist for the article
- **THEN** the API returns 404 and nothing changes

### Requirement: Delete a snapshot
The writer API SHALL delete a snapshot the article does not currently point to and return 204. Only that snapshot SHALL be removed; the draft, status, `published_at`, snapshot counter, and other snapshots SHALL be unchanged. A missing snapshot, or one belonging to another article, SHALL return 404.

#### Scenario: Delete a historical snapshot
- **WHEN** a published article has snapshots 1, 2, and 3 with 3 live, and the writer deletes snapshot 1
- **THEN** the API returns 204 and the article has exactly snapshots 2 and 3

#### Scenario: Delete a historical snapshot of an unpublished article
- **WHEN** an article has snapshots 1, 2, and 3, its status is `unpublished`, its reference to the last published snapshot still names snapshot 3, and the writer deletes snapshot 1
- **THEN** the API returns 204 and the article has exactly snapshots 2 and 3
- **AND** the status is still `unpublished` and the reference still names snapshot 3

#### Scenario: Delete a missing snapshot
- **WHEN** the writer deletes a snapshot id that does not exist for the article
- **THEN** the API returns 404

### Requirement: The pointed-to snapshot cannot be deleted
The API SHALL reject, with 409, deleting the snapshot an article currently points to. This SHALL hold while the article is `published` and also while it is `unpublished`, so the last published snapshot is always kept. The database itself SHALL also refuse the deletion.

#### Scenario: Delete the live snapshot
- **WHEN** the writer deletes the snapshot a published article points to
- **THEN** the API returns 409 and the snapshot still exists and is still live

#### Scenario: Delete the last published snapshot after unpublishing
- **WHEN** an article is unpublished and the writer deletes the snapshot it still points to
- **THEN** the API returns 409 and the snapshot still exists

#### Scenario: Freeing the last published snapshot by republishing
- **WHEN** an unpublished article is published again, moving its pointer to a new snapshot
- **THEN** the previously pointed-to snapshot can be deleted with 204

#### Scenario: Database refuses the deletion directly
- **WHEN** a direct database delete is attempted on the snapshot an article points to
- **THEN** the database rejects it and the snapshot still exists
