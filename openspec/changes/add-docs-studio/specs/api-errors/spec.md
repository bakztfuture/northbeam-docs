# Spec Delta

## Purpose

Gives every API consumer one predictable error shape and correct status codes, maps expected database failures to meaningful responses, and never leaks internal details when something unexpected goes wrong.

## ADDED Requirements

### Requirement: Flat error response for known errors
Every known application error (404, 409, 503, and others raised deliberately) SHALL be returned as a flat JSON object with a numeric `code` equal to the HTTP status, a human-readable `title`, and an optional `message` with more context. There SHALL be no nested error object.

#### Scenario: Draft conflict response
- **WHEN** a draft save is rejected because the draft version is stale
- **THEN** the response status is 409 and the body is `{"code": 409, "title": "Draft conflict", "message": "..."}`

#### Scenario: Not found without a message
- **WHEN** a writer requests an article that does not exist
- **THEN** the response status is 404 and the body has `code` 404 and a `title`, and may omit `message`

### Requirement: Validation errors use the framework default
Requests whose body, path, or query fail validation SHALL return 422 with the framework's standard validation error body, unchanged. This includes malformed article and snapshot ids in the path.

#### Scenario: Malformed id
- **WHEN** a request uses an article id that is not a valid UUID
- **THEN** the API returns 422 with the standard validation body

#### Scenario: Missing required field
- **WHEN** a draft save omits `expectedDraftVersion`
- **THEN** the API returns 422 with the standard validation body

### Requirement: Expected database conflicts return 409
When the database rejects a write because of a uniqueness rule or because a protected snapshot is still referenced, the API SHALL return 409 in the flat error format, even if application checks did not catch it first.

#### Scenario: Slug race reaches the database
- **WHEN** two requests create articles with the same slug at the same time and the database rejects the second
- **THEN** the second request returns 409, not 500

#### Scenario: Protected snapshot reaches the database
- **WHEN** a delete of the pointed-to snapshot reaches the database and is rejected there
- **THEN** the request returns 409, not 500

### Requirement: Database busy returns 503
When a write cannot get the database lock within the configured busy timeout, the API SHALL return 503 with a message saying the database is busy. It SHALL NOT send a `Retry-After` header or suggest retrying, and neither the server nor the UI SHALL retry automatically. Any partial transaction SHALL be rolled back first.

#### Scenario: Database is locked
- **WHEN** another connection holds the write lock for longer than the busy timeout and a writer saves a draft
- **THEN** the API returns 503 with `{"code": 503, "title": "Service temporarily unavailable", "message": "The database is busy."}` and no `Retry-After` header
- **AND** the draft is unchanged and later writes succeed once the lock is released

### Requirement: Unexpected errors are generic
Any other failure SHALL return 500 with `{"code": 500, "title": "Internal server error"}`. The response SHALL NOT include SQL, stack traces, file paths, or connection details; the full error SHALL be logged on the server. Integrity violations that indicate a bug, such as a broken consistency rule, SHALL return 500.

#### Scenario: Unhandled exception
- **WHEN** a request fails with an unexpected exception
- **THEN** the API returns 500 with only `code` and `title`
- **AND** the exception details are written to the server log

### Requirement: Failed writes leave no partial changes
Whenever a write request fails, for any reason, every database change made during that request SHALL be rolled back before the error response is sent, and the database lock SHALL be released.

#### Scenario: Write fails partway
- **WHEN** a write request fails after some of its statements have run
- **THEN** none of its changes are stored and the next write request is not blocked
