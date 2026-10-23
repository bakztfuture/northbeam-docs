# Spec Delta

## Purpose

Gives the internal writer a minimal browser interface over the writer API (article list, create form, editor with preview, publish controls, and version history) that protects unsaved work and makes publication state visible.

## ADDED Requirements

### Requirement: Article list
The writer UI SHALL list every article with its title, slug, and status, let the writer open an article, and let the writer start a new one.

#### Scenario: Writer sees all articles
- **WHEN** the writer opens the admin
- **THEN** every article is listed with its status (`draft`, `published`, or `unpublished`)

### Requirement: Create an article from a local form
Starting a new article SHALL open a form held only in the browser; nothing SHALL be stored until the writer saves. The first save SHALL create the article, and the editor SHALL then switch to editing that article. A slug already in use SHALL show an error and keep the form's content.

#### Scenario: First save creates the article
- **WHEN** the writer fills in title, slug, body, and tags and saves
- **THEN** the article is created and the editor shows it with status `draft` and draft version 1

#### Scenario: Abandoned new article stores nothing
- **WHEN** the writer starts a new article and leaves without saving
- **THEN** no article is created

#### Scenario: Slug taken
- **WHEN** the first save fails because the slug is already in use
- **THEN** the form shows the error and keeps everything the writer typed

### Requirement: Editor
The editor SHALL show editable title, Markdown body, and tags; the slug read-only once the article exists; the article's status, draft version, and `published_at`; an explicit Save action; and a live Markdown preview of the current editor content.

#### Scenario: Slug is read-only after creation
- **WHEN** the writer opens an existing article
- **THEN** the slug is shown but cannot be edited

#### Scenario: Preview follows typing (FE)
- **WHEN** the writer edits the body
- **THEN** the preview updates to show the unsaved content

### Requirement: Publish is disabled while there are unsaved changes
**Publish snapshots the saved draft, not the editor's contents.** So the UI SHALL disable Publish whenever the editor differs from the last saved draft, and SHALL tell the writer to save first. Publish SHALL be enabled again once the changes are saved.

#### Scenario: Unsaved edits block publishing
- **WHEN** the writer changes the title, body, or tags without saving
- **THEN** the Publish button is disabled and the message "Save your changes before publishing" is shown

#### Scenario: Saving re-enables publishing
- **WHEN** the writer saves those changes successfully
- **THEN** the Publish button is enabled

#### Scenario: Reverting edits re-enables publishing
- **WHEN** the writer changes the body and then changes it back to the saved text
- **THEN** the Publish button is enabled

### Requirement: Publish and unpublish controls
The editor SHALL offer Publish for any article and Unpublish only for a `published` article, sending the loaded draft version with Publish. After either action, the status, published snapshot reference, `published_at`, and history SHALL refresh.

#### Scenario: Publish from the editor
- **WHEN** the writer publishes a saved draft and confirms
- **THEN** the status shows `published` and the new snapshot appears at the top of the history

#### Scenario: Unpublish is only offered when published
- **WHEN** the article is `draft` or `unpublished`
- **THEN** no Unpublish action is available

### Requirement: Publish asks for confirmation
Choosing Publish SHALL open a confirmation dialog explaining that readers will see the saved draft immediately. The publish request SHALL be sent only if the writer confirms; cancelling or dismissing the dialog SHALL send nothing and change nothing.

#### Scenario: Confirm publishes (FE)
- **WHEN** the writer chooses Publish and confirms in the dialog
- **THEN** exactly one publish request is sent and the new snapshot appears in the history

#### Scenario: Cancel does nothing (FE)
- **WHEN** the writer chooses Publish and then cancels, presses Escape, or clicks outside the dialog
- **THEN** no request is sent and the article is unchanged

### Requirement: One action at a time
While a save, publish, unpublish, restore, delete, or reload request is in progress, the editor SHALL NOT start any other of these actions. For actions that ask for confirmation, this begins only once the writer confirms. Their controls SHALL be disabled, the in-progress action SHALL show that it is working, and every control SHALL become available again when it finishes, whether it succeeded or failed.

#### Scenario: Restore during a save (FE)
- **WHEN** a save is in progress and the writer tries to restore a snapshot
- **THEN** Restore is unavailable and no restore request is sent

#### Scenario: Waiting for confirmation does not lock (FE)
- **WHEN** the publish confirmation is open and the writer cancels it
- **THEN** no control was ever disabled by it and every control is available

#### Scenario: Controls return after a failure (FE)
- **WHEN** an in-progress save fails with an error
- **THEN** the error is shown and every control is available again

### Requirement: Draft conflicts keep the writer's work
When a save, restore, or publish returns 409 because the draft changed elsewhere, the UI SHALL explain the conflict and SHALL keep the writer's unsaved content in the editor. It SHALL offer to reload the latest draft, which replaces the editor content only after the writer confirms.

#### Scenario: Save conflict
- **WHEN** the writer saves and the API returns 409
- **THEN** a conflict message is shown and the editor still contains the writer's text

#### Scenario: Reload latest after a conflict
- **WHEN** the writer chooses to reload the latest draft and confirms
- **THEN** the editor shows the latest saved draft and its current draft version

### Requirement: Version history panel
The editor SHALL show the article's snapshots newest first with version number and creation time, mark the snapshot the article points to, and let the writer view a snapshot rendered, restore it into the draft, or delete it.

#### Scenario: View a snapshot
- **WHEN** the writer selects a snapshot in the history
- **THEN** its title, tags, and rendered body are shown

#### Scenario: Restore from history
- **WHEN** the writer restores a snapshot
- **THEN** the editor shows the restored content as the saved draft with the new draft version, and the article is not published

#### Scenario: Restore with unsaved edits asks first
- **WHEN** the writer has unsaved changes and chooses to restore a snapshot
- **THEN** the UI asks for confirmation before replacing the editor content

### Requirement: Protected snapshot is explained
The history panel SHALL not offer Delete for the snapshot the article points to, and SHALL explain that it cannot be deleted while it is the article's current or last published version. Deleting any other snapshot SHALL ask for confirmation first.

#### Scenario: Pointed-to snapshot
- **WHEN** the history shows the snapshot the article points to
- **THEN** its Delete action is unavailable with an explanation

#### Scenario: Delete another snapshot
- **WHEN** the writer deletes a different snapshot and confirms
- **THEN** it disappears from the history
