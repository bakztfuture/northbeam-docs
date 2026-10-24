// Mirrors the API's request and response shapes (design Decision 5). Ids are UUID strings;
// timestamps are UTC ISO 8601 strings with milliseconds.

export type ArticleStatus = 'draft' | 'published' | 'unpublished'

// --- Responses ---

export interface Draft {
  title: string
  body: string
  tags: string[]
}

export interface AdminArticle {
  id: string
  slug: string
  status: ArticleStatus
  draft: Draft
  draftVersion: number
  currentPublishedVersionId: string | null
  publishedAt: string | null
  createdAt: string
  updatedAt: string
}

export interface ArticleListItem {
  id: string
  slug: string
  title: string
  status: ArticleStatus
  updatedAt: string
}

export interface Snapshot {
  id: string
  versionNumber: number
  title: string
  body: string
  tags: string[]
  createdAt: string
  isCurrent: boolean
}

export interface SnapshotListItem {
  id: string
  versionNumber: number
  title: string
  createdAt: string
  isCurrent: boolean
}

export interface PublishedArticle {
  article: AdminArticle
  snapshot: Snapshot
}

export interface PublicArticle {
  slug: string
  title: string
  body: string
  tags: string[]
  publishedAt: string
}

export interface PublicArticleListItem {
  slug: string
  title: string
  tags: string[]
  publishedAt: string
}

// --- Requests ---

export interface CreateArticleRequest {
  title: string
  slug: string
  body: string
  tags: string[]
}

export interface SaveDraftRequest {
  title: string
  body: string
  tags: string[]
  expectedDraftVersion: number
}
