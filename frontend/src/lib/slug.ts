// New articles get a random slug instead of one the writer types (design Decision 8): 10
// lowercase letters, about 1.4 × 10^14 possibilities, so a clash is practically impossible.

const letters = 'abcdefghijklmnopqrstuvwxyz'

export function randomSlug(length = 10): string {
  const values = crypto.getRandomValues(new Uint32Array(length))
  return Array.from(values, (value) => letters[value % letters.length]).join('')
}
