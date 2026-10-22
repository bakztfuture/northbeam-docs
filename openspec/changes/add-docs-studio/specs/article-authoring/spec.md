# Spec Delta

## Purpose

Lets an internal writer create documentation articles and edit each article's single mutable draft without ever affecting published content, and detects conflicting edits instead of silently overwriting them.

## ADDED Requirements

### Requirement: Create an article
The writer API SHALL create an article from a title, slug, Markdown body, and tags. A new article SHALL have status `draft`, draft version 1, no published snapshot reference, no `published_at`, and no snapshots. It SHALL NOT be visible through the public API.

#### Scenario: Article is created as a draft
- **WHEN** the writer creates an article with title "Getting Started", slug "getting-started", body "# Welcome", and tags ["guide"]
- **THEN** the API returns 201 with the article's id, status `draft`, draft version 1, and the submitted draft fields
- **AND** the article has no snapshots and no `published_at`

#### Scenario: New article is not public
- **WHEN** an article has just been created
- **THEN** a public read of its slug returns 404

### Requirement: Slugs are unique
Each article's slug SHALL be unique across all articles. Creating an article with a slug that is already in use SHALL be rejected with 409 and SHALL NOT create anything.

#### Scenario: Duplicate slug is rejected
- **WHEN** an article with slug "getting-started" exists and the writer creates another with the same slug
- **THEN** the API returns 409 and no second article is created

### Requirement: Slugs are fixed after creation
An article's slug SHALL be set only when the article is created and SHALL NOT be changeable afterwards. Draft saves SHALL NOT accept a slug.

#### Scenario: Draft save cannot change the slug
- **WHEN** the writer saves a draft and the request includes a slug field
- **THEN** the API returns 422 and the slug is not changed

### Requirement: Validate article input
The API SHALL reject invalid input with 422. A slug SHALL be 1 to 100 characters of lowercase letters, digits, and single hyphens between them. Title and body SHALL contain at least one non-whitespace character; the title SHALL be at most 200 characters and the body at most 50,000. Tags SHALL be a list of at most 20 non-blank strings of at most 100 characters each, stored trimmed, lowercased, and without duplicates, in first-seen order.

#### Scenario: Invalid slug is rejected
- **WHEN** the writer creates an article with slug "Getting Started!"
- **THEN** the API returns 422 and nothing is created

#### Scenario: Blank body is rejected
- **WHEN** the writer creates an article or saves a draft with a body containing only whitespace
- **THEN** the API returns 422 and nothing is changed

#### Scenario: Blank title is rejected
- **WHEN** the writer submits a title containing only whitespace
- **THEN** the API returns 422

#### Scenario: Tags are normalized
- **WHEN** the writer submits tags [" Guide ", "guide", "API"]
- **THEN** the stored tags are ["guide", "api"]

#### Scenario: Blank tag is rejected
- **WHEN** the writer submits tags ["guide", "  "]
- **THEN** the API returns 422

#### Scenario: Body too long is rejected
- **WHEN** the writer creates an article or saves a draft with a body of 50,001 characters
- **THEN** the API returns 422 and nothing is changed

#### Scenario: Tag too long is rejected
- **WHEN** the writer submits a tag of 101 characters
- **THEN** the API returns 422 and nothing is changed

#### Scenario: Too many tags are rejected
- **WHEN** the writer submits 21 tags
- **THEN** the API returns 422 and nothing is changed

### Requirement: List and read articles for the writer
The writer API SHALL list all articles regardless of status, and SHALL return a single article with its current draft fields, draft version, status, slug, published snapshot reference, and `published_at`. An unknown article id SHALL return 404.

#### Scenario: Writer list includes every status
- **WHEN** articles exist in `draft`, `published`, and `unpublished` status
- **THEN** the writer list contains all of them with their statuses

#### Scenario: Unknown article
- **WHEN** the writer requests an article id that does not exist
- **THEN** the API returns 404

### Requirement: Save the draft
The writer API SHALL replace an article's draft title, body, and tags with the submitted values and increment its draft version by one. Saving SHALL NOT create, change, or delete any snapshot, and SHALL NOT change the article's status, published snapshot reference, or `published_at`.

#### Scenario: Draft is saved
- **WHEN** the writer saves new content with the article's current draft version
- **THEN** the API returns 200 with the new content and the draft version increased by one

#### Scenario: Saving does not affect published content
- **WHEN** a published article's draft is saved with new content
- **THEN** a public read of the article still returns the previously published content
- **AND** the number of snapshots is unchanged

### Requirement: Detect stale draft writes
Every draft save SHALL include the draft version the writer last loaded. If it does not match the article's current draft version, the save SHALL be rejected with 409 and a clear "Draft conflict" error saying the draft changed since it was loaded, and the draft SHALL be left unchanged.

#### Scenario: Second writer with an old copy is rejected
- **WHEN** two writers load the same draft at version 3, the first saves successfully, and the second then saves with version 3
- **THEN** the second save returns 409 with title "Draft conflict"
- **AND** the draft still contains the first writer's content at version 4

#### Scenario: Saving a missing article
- **WHEN** the writer saves a draft for an article id that does not exist
- **THEN** the API returns 404

### Requirement: Draft changes are tracked by update time
The article's `updated_at` SHALL change when its draft changes (create, save, restore) and SHALL NOT change when it is published, unpublished, or when a snapshot is deleted.

#### Scenario: Publishing does not touch updated_at
- **WHEN** an article is published
- **THEN** its `updated_at` is the same as before the publish
