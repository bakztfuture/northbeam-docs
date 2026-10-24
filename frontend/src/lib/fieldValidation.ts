// The validation rules for the article form's fields, checked in the browser before a save.
// They mirror the API's Pydantic models (design Decision 6), which stay the authority: anything
// that slips past here is still rejected with 422.

export const TITLE_MAX = 200
export const BODY_MAX = 50_000
export const TAGS_MAX = 20
export const TAG_MAX = 100

// Tags are edited as one comma-separated string. Blank entries are dropped; the API also trims,
// lowercases, and removes duplicates.
export function parseTags(text: string): string[] {
  return text
    .split(',')
    .map((tag) => tag.trim())
    .filter(Boolean)
}

// A message for the field, or '' when it is fine. `required` and `maxlength` on the inputs
// cover empty and too-long values; these cover what they cannot.
export function blankProblem(value: string, field: string): string {
  return value !== '' && value.trim() === '' ? `${field} can't be only spaces.` : ''
}

export function tagsProblem(text: string): string {
  const tags = parseTags(text)
  if (tags.length > TAGS_MAX) return `Use at most ${TAGS_MAX} tags.`
  if (tags.some((tag) => tag.length > TAG_MAX)) {
    return `Each tag can be at most ${TAG_MAX} characters.`
  }
  return ''
}
