// An in-memory stand-in for the API, answered from inside the test with page.route(), so no
// backend or database runs. It follows the documented rules (design Decision 5) for the
// endpoints the checks touch: drafts with a version check, publish, unpublish, the snapshot
// list, and the public reads. Responses are typed with the frontend's own types, so a change
// to the API's shapes shows up as a type error here.
import type { Page, Route } from '@playwright/test'
import type {
  AdminArticle,
  ArticleListItem,
  PublicArticle,
  PublicArticleListItem,
  Snapshot,
  SnapshotListItem,
} from '../src/services/types'

interface StoredArticle {
  article: AdminArticle
  snapshots: Snapshot[] // newest first
  lastVersionNumber: number
}

const now = () => new Date().toISOString()

export class FakeApi {
  private readonly articles = new Map<string, StoredArticle>()
  private nextId = 1
  // Requests the fake has no answer for; each check asserts this stays empty.
  readonly unhandled: string[] = []

  // An article that already exists, as if created earlier.
  seedArticle(draft: { title: string; body: string; tags?: string[] }): AdminArticle {
    return this.create({ slug: `seeded${this.nextId}`, tags: [], ...draft })
  }

  // Another tab saving the same draft: the version moves on, so the page's next save is stale.
  editElsewhere(id: string, changes: Partial<AdminArticle['draft']>) {
    const stored = this.mustGet(id)
    stored.article.draft = { ...stored.article.draft, ...changes }
    stored.article.draftVersion += 1
    stored.article.updatedAt = now()
  }

  async install(page: Page) {
    await page.route('**/api/**', (route) => this.handle(route))
  }

  private create(input: { title: string; slug: string; body: string; tags: string[] }) {
    const id = `00000000-0000-4000-8000-${String(this.nextId++).padStart(12, '0')}`
    const time = now()
    const article: AdminArticle = {
      id,
      slug: input.slug,
      status: 'draft',
      draft: { title: input.title, body: input.body, tags: input.tags },
      draftVersion: 1,
      currentPublishedVersionId: null,
      publishedAt: null,
      createdAt: time,
      updatedAt: time,
    }
    this.articles.set(id, { article, snapshots: [], lastVersionNumber: 0 })
    return article
  }

  private mustGet(id: string): StoredArticle {
    const stored = this.articles.get(id)
    if (!stored) throw new Error(`FakeApi: no article ${id}`)
    return stored
  }

  private bySlug(slug: string) {
    return [...this.articles.values()].find((s) => s.article.slug === slug)
  }

  private async handle(route: Route) {
    const request = route.request()
    const method = request.method()
    const path = new URL(request.url()).pathname.replace(/^\/api/, '')
    const body: unknown = request.postDataJSON()
    let match: RegExpMatchArray | null

    // --- Admin ---
    if (method === 'GET' && path === '/admin/articles') {
      const list: ArticleListItem[] = [...this.articles.values()].map(({ article }) => ({
        id: article.id,
        slug: article.slug,
        title: article.draft.title,
        status: article.status,
        updatedAt: article.updatedAt,
      }))
      return json(route, 200, list)
    }
    if (method === 'POST' && path === '/admin/articles') {
      const input = body as { title: string; slug: string; body: string; tags: string[] }
      if (this.bySlug(input.slug)) return error(route, 409, 'Slug already exists')
      return json(route, 201, this.create(input))
    }
    if ((match = path.match(/^\/admin\/articles\/([^/]+)(\/.*)?$/))) {
      const stored = this.articles.get(match[1]!)
      if (!stored) return error(route, 404, 'Article not found')
      const { article } = stored
      const rest = match[2] ?? ''

      if (method === 'GET' && rest === '') return json(route, 200, article)
      if (method === 'PATCH' && rest === '/draft') {
        const input = body as AdminArticle['draft'] & { expectedDraftVersion: number }
        if (input.expectedDraftVersion !== article.draftVersion) return draftConflict(route)
        article.draft = { title: input.title, body: input.body, tags: input.tags }
        article.draftVersion += 1
        article.updatedAt = now()
        return json(route, 200, article)
      }
      if (method === 'POST' && rest === '/publish') {
        if (
          (body as { expectedDraftVersion: number }).expectedDraftVersion !== article.draftVersion
        ) {
          return draftConflict(route)
        }
        stored.lastVersionNumber += 1
        const snapshot: Snapshot = {
          id: `snapshot-${article.id}-${stored.lastVersionNumber}`,
          versionNumber: stored.lastVersionNumber,
          ...article.draft,
          createdAt: now(),
          isCurrent: true,
        }
        stored.snapshots.forEach((s) => (s.isCurrent = false))
        stored.snapshots.unshift(snapshot)
        article.status = 'published'
        article.currentPublishedVersionId = snapshot.id
        article.publishedAt ??= snapshot.createdAt
        return json(route, 201, { article, snapshot })
      }
      if (method === 'POST' && rest === '/unpublish') {
        if (article.status !== 'published') return error(route, 409, 'Article is not published')
        article.status = 'unpublished'
        return json(route, 200, article)
      }
      if (method === 'GET' && rest === '/snapshots') {
        const list: SnapshotListItem[] = stored.snapshots.map((s) => ({
          id: s.id,
          versionNumber: s.versionNumber,
          title: s.title,
          createdAt: s.createdAt,
          isCurrent: s.isCurrent,
        }))
        return json(route, 200, list)
      }
    }

    // --- Public: published articles only, always from the live snapshot ---
    const live = (stored: StoredArticle) =>
      stored.article.status === 'published' ? stored.snapshots.find((s) => s.isCurrent) : undefined
    if (method === 'GET' && path === '/public/articles') {
      const list: PublicArticleListItem[] = []
      for (const stored of this.articles.values()) {
        const snapshot = live(stored)
        if (snapshot) {
          const { slug, publishedAt } = stored.article
          list.push({ slug, title: snapshot.title, tags: snapshot.tags, publishedAt: publishedAt! })
        }
      }
      return json(route, 200, list)
    }
    if (method === 'GET' && (match = path.match(/^\/public\/articles\/([^/]+)$/))) {
      const stored = this.bySlug(decodeURIComponent(match[1]!))
      const snapshot = stored && live(stored)
      if (!stored || !snapshot) return error(route, 404, 'Article not found')
      const article: PublicArticle = {
        slug: stored.article.slug,
        title: snapshot.title,
        body: snapshot.body,
        tags: snapshot.tags,
        publishedAt: stored.article.publishedAt!,
      }
      return json(route, 200, article)
    }

    // Anything else would have gone to the real backend: refuse it and record it.
    this.unhandled.push(`${method} ${path}`)
    return error(route, 501, 'Not handled by the fake API')
  }
}

function json(route: Route, status: number, body: unknown) {
  return route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
}

// The API's flat error body: {code, title, message?}.
function error(route: Route, code: number, title: string, message?: string) {
  return json(route, code, message ? { code, title, message } : { code, title })
}

function draftConflict(route: Route) {
  return error(route, 409, 'Draft conflict', 'The draft changed since it was loaded.')
}
