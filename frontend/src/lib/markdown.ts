// The one Markdown renderer, shared by the draft preview, snapshot views, and public pages.
import MarkdownIt from 'markdown-it'

// html: false escapes raw HTML instead of rendering it. markdown-it's default validateLink
// already drops javascript:, vbscript:, file:, and non-image data: URLs, so it is kept as is.
const markdown = new MarkdownIt({ html: false })

export function renderMarkdown(source: string): string {
  return markdown.render(source)
}
