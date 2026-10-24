# markdown-rendering Specification

## Purpose

Renders article Markdown consistently and safely wherever it is shown (draft preview, snapshot history, and public pages) while the backend stores and returns Markdown only as plain text.

## Requirements

### Requirement: Markdown is stored and returned as plain text
The backend SHALL store article and snapshot bodies exactly as submitted Markdown text and SHALL return them unchanged. It SHALL NOT convert Markdown to HTML and SHALL NOT offer a rendering endpoint.

#### Scenario: Body round-trips unchanged
- **WHEN** a body containing headings, lists, and a fenced code block is saved and read back
- **THEN** the returned body is identical to the submitted text

### Requirement: One renderer for every view
The frontend SHALL render Markdown with a single shared renderer for the draft preview, snapshot views, and public article pages, so the same Markdown looks the same everywhere. It SHALL support headings, bold, italic, ordered and unordered lists, links, blockquotes, inline code, and fenced code blocks.

#### Scenario: Supported formatting renders (FE)
- **WHEN** Markdown containing each supported element is rendered
- **THEN** each element is rendered as its formatted equivalent

#### Scenario: Snapshot view shows the stored snapshot (FE)
- **WHEN** the writer views a historical snapshot
- **THEN** the rendered content is the snapshot's body, not the draft

### Requirement: Rendering is safe
The renderer SHALL NOT render raw HTML embedded in Markdown and SHALL NOT produce links with unsafe protocols: `javascript:`, `vbscript:`, `file:`, or `data:` URLs other than images.

#### Scenario: Raw HTML is not rendered (FE)
- **WHEN** a body contains `<script>alert(1)</script>` or `<img onerror=...>`
- **THEN** the output contains no such element and no script runs

#### Scenario: Unsafe link is neutralized (FE)
- **WHEN** a body contains `[click](javascript:alert(1))`
- **THEN** the output contains no link with a `javascript:` target

### Requirement: Preview has no side effects
The draft preview SHALL render the editor's current content, including unsaved changes, entirely in the browser, and SHALL NOT send any request or change any stored data.

#### Scenario: Preview of unsaved text (FE)
- **WHEN** the writer types new Markdown without saving
- **THEN** the preview shows it rendered and no request is sent to the API
