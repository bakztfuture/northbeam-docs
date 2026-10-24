# writer-ui Specification

## Purpose

Gives the internal writer a minimal browser interface over the writer API (article list, create form, editor with preview, publish controls, and version history) that protects unsaved work and makes publication state visible.

## Requirements

### Requirement: Article list
The writer UI SHALL list every article with its title, slug, and status, let the writer open an article, and let the writer start a new one.

#### Scenario: Writer sees all articles
- **WHEN** the writer opens the admin
- **THEN** every article is listed with its status (`draft`, `published`, or `unpublished`)

### Requirement: Create an article from a local form
Starting a new article SHALL open a form held only in the browser; nothing SHALL be stored until the writer saves. The form SHALL NOT ask for a slug: it SHALL generate one of random lowercase letters and send it with the first save. The first save SHALL create the article, and the editor SHALL then switch to editing that article. A slug already in use SHALL show an error, keep the form's content, and generate a new slug for the next save.

#### Scenario: First save creates the article
- **WHEN** the writer fills in title, body, and tags and saves
- **THEN** the article is created with the generated slug, and the editor shows it with status `draft` and draft version 1

#### Scenario: New form has no slug field (FE)
- **WHEN** the writer starts a new article
- **THEN** the form shows no slug field, and the slug sent on the first save is made only of lowercase letters

#### Scenario: Abandoned new article stores nothing
- **WHEN** the writer starts a new article and leaves without saving
- **THEN** no article is created

#### Scenario: Slug taken
- **WHEN** the first save fails because the slug is already in use
- **THEN** the form shows the error, keeps everything the writer typed, and the next save sends a newly generated slug

### Requirement: Editor
The editor SHALL show editable title, Markdown body, and tags; the slug, read-only, once the article exists; the article's status, draft version, and `published_at`; an explicit Save action; and a Preview tab beside the body with a live Markdown render of the current editor content.

#### Scenario: Slug is read-only after creation
- **WHEN** the writer opens an existing article
- **THEN** the slug is shown but cannot be edited

#### Scenario: Preview follows typing (FE)
- **WHEN** the writer edits the body and opens the Preview tab
- **THEN** the preview shows the unsaved content

### Requirement: Input is checked before saving
Before a save, the editor SHALL check in the browser that the title and main content are filled in and not only spaces, and that the title, body, and tags are within the API's limits. If a check fails, it SHALL show a message on the field and send nothing.

#### Scenario: Missing title is caught before saving (FE)
- **WHEN** the writer clears the title and chooses Save
- **THEN** a message is shown on the title field and no request is sent

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
The editor SHALL offer Publish for any article and Unpublish only for a `published` article, sending the loaded draft version with Publish. After a successful publish, the UI SHALL take the writer to the article's public page, so they see what readers now see. After a successful unpublish, it SHALL take the writer to the public article list, where the article no longer appears. If either action fails, the writer SHALL stay in the editor with the error shown.

#### Scenario: Publish from the editor
- **WHEN** the writer publishes a saved draft and confirms
- **THEN** the article's public page opens and shows the new snapshot's content, and returning to the editor shows status `published` with the new snapshot at the top of the history

#### Scenario: Unpublish from the editor (FE)
- **WHEN** the writer unpublishes a published article
- **THEN** the public article list opens and the article is not in it

#### Scenario: Unpublish is only offered when published
- **WHEN** the article is `draft` or `unpublished`
- **THEN** no Unpublish action is available

### Requirement: Publish asks for confirmation
Choosing Publish SHALL open a confirmation dialog explaining that readers will see the saved draft immediately. The publish request SHALL be sent only if the writer confirms; cancelling or dismissing the dialog SHALL send nothing and change nothing.

#### Scenario: Confirm publishes (FE)
- **WHEN** the writer chooses Publish and confirms in the dialog
- **THEN** exactly one publish request is sent and the article's public page opens

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
When a save, restore, or publish returns 409 because the draft changed elsewhere, the UI SHALL explain the conflict and SHALL keep the writer's unsaved content in the editor. It SHALL offer to reload the latest draft, which replaces the editor content straight away, with no confirmation dialog; the conflict message already says the unsaved edits will be replaced.

#### Scenario: Save conflict
- **WHEN** the writer saves and the API returns 409
- **THEN** a conflict message is shown and the editor still contains the writer's text

#### Scenario: Reload latest after a conflict
- **WHEN** the writer chooses to reload the latest draft
- **THEN** the editor shows the latest saved draft and its current draft version

### Requirement: Version history panel
The editor SHALL show all of the article's snapshots, newest first, with version number and creation time, mark the snapshot the article points to, and let the writer view a snapshot rendered, restore it into the draft, or delete it. A long history SHALL scroll inside the panel rather than stretch the page.

#### Scenario: View a snapshot
- **WHEN** the writer selects a snapshot in the history
- **THEN** its title, tags, and rendered body are shown

#### Scenario: Every snapshot is listed (FE)
- **WHEN** an article has many snapshots
- **THEN** the history lists every one, newest first, and scrolls inside the panel

#### Scenario: Restore from history
- **WHEN** the writer restores a snapshot
- **THEN** the editor shows the restored content as the saved draft with the new draft version, and the article is not published

#### Scenario: Restore replaces unsaved edits without asking (FE)
- **WHEN** the writer has unsaved changes and chooses to restore a snapshot
- **THEN** the snapshot is restored straight away, with no confirmation dialog, and replaces the unsaved edits

### Requirement: Protected snapshot is explained
The history panel SHALL not offer Delete for the snapshot the article points to, and SHALL explain that it cannot be deleted while it is the article's current or last published version. Deleting any other snapshot SHALL happen straight away, with no confirmation dialog; Publish is the only action that asks first.

#### Scenario: Pointed-to snapshot
- **WHEN** the history shows the snapshot the article points to
- **THEN** its Delete action is unavailable with an explanation

#### Scenario: Delete another snapshot
- **WHEN** the writer deletes a different snapshot
- **THEN** it disappears from the history
