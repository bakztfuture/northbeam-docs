# Spec Delta

## Purpose

Lets anonymous readers on the public docs site browse and read published articles, always from each article's live snapshot, and reveals nothing about drafts or unpublished articles.

## ADDED Requirements

### Requirement: List published articles
The public API SHALL list only articles whose status is `published`, each with its slug, title, tags, and `published_at`, ordered newest `published_at` first. Title and tags SHALL come from the article's live snapshot, not its draft. Draft-only and unpublished articles SHALL NOT appear. No authentication SHALL be required.

#### Scenario: Only published articles are listed
- **WHEN** one article is `published`, one is `draft`, and one is `unpublished`
- **THEN** the public list contains only the published article

#### Scenario: List shows snapshot data, not the draft
- **WHEN** a published article's draft title and tags are changed and saved but not published
- **THEN** the public list still shows the live snapshot's title and tags

#### Scenario: Newest first
- **WHEN** article A was first published before article B
- **THEN** the public list shows B before A

#### Scenario: List shows the first publication time
- **WHEN** an article was first published, then republished later
- **THEN** the public list shows the time of the first publish

### Requirement: Read a published article
The public API SHALL return a published article by slug with its title, Markdown body, tags, and `published_at`, all taken from its live snapshot, never from the draft. No authentication SHALL be required.

#### Scenario: Read returns the live snapshot
- **WHEN** a reader requests the slug of a published article
- **THEN** the API returns 200 with the live snapshot's title, body, and tags

#### Scenario: Draft edits are not visible
- **WHEN** a published article's draft is edited and saved but not published
- **THEN** a public read returns the live snapshot's content, not the edited draft

#### Scenario: Republish changes what readers see
- **WHEN** an edited draft is published
- **THEN** a public read returns the new snapshot's content

### Requirement: Hide everything that is not published
A public read of a slug that is draft-only, unpublished, or does not exist SHALL return 404 with the same response in every case, and SHALL NOT include any draft or snapshot content.

#### Scenario: Draft-only article
- **WHEN** a reader requests the slug of an article that has never been published
- **THEN** the API returns 404 and no article content

#### Scenario: Unpublished article
- **WHEN** a reader requests the slug of an article that was published and then unpublished
- **THEN** the API returns 404 and no article content

#### Scenario: Unknown slug
- **WHEN** a reader requests a slug that matches no article
- **THEN** the API returns 404, identical to the draft-only and unpublished cases

### Requirement: Public reader pages
The frontend SHALL provide a public list page showing each published article's title, tags, and publication date, and an article page that renders the live snapshot's Markdown. An article the API reports as not found SHALL show a "not found" page.

#### Scenario: Reader opens an article
- **WHEN** a reader selects an article from the public list
- **THEN** the article page shows its title, tags, publication date, and rendered body

#### Scenario: Reader opens a hidden article
- **WHEN** a reader opens the page for an unpublished article's slug
- **THEN** the page shows "not found" and no content
