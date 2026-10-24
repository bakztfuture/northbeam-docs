import { parseTags } from '../../lib/fieldValidation'
import type { AdminArticle } from '../../services/types'

// What is in the editor's inputs. Tags are edited as one comma-separated string. The slug is
// not an input: a new article gets a random one, and an existing one's is fixed.
export interface ArticleFormFields {
  title: string
  body: string
  tags: string
}

// What a new article starts with: a placeholder title and a body that shows the supported
// Markdown, for the writer to replace. Nothing is stored until the first save.
export const starterForm: ArticleFormFields = {
  title: 'Untitled article',
  body: [
    '# Overview',
    '',
    'Summarize what this article covers in a sentence or two.',
    '',
    '## Steps',
    '',
    '1. Describe the first step.',
    '2. Describe the next one.',
    '',
    '## Notes',
    '',
    '- Use **bold** and *italic* for emphasis.',
    '- Link to related docs, like [the Northbeam Docs home](/).',
    '- Put commands in `inline code` or a code block:',
    '',
    '```bash',
    'nb --help',
    '```',
    '',
    '> Tip: open the Preview tab to see how this will look to readers.',
    '',
  ].join('\n'),
  tags: '',
}

// The inputs for a saved article's draft.
export function toForm(article: AdminArticle): ArticleFormFields {
  const { title, body, tags } = article.draft
  return { title, body, tags: tags.join(', ') }
}

// Whether the inputs differ from `base` in anything that would be saved. Tags are compared as
// parsed lists, so a trailing comma or extra spaces do not count as a change.
export function formsDiffer(current: ArticleFormFields, base: ArticleFormFields): boolean {
  return (
    current.title !== base.title ||
    current.body !== base.body ||
    parseTags(current.tags).join('\n') !== parseTags(base.tags).join('\n')
  )
}
