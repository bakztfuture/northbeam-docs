// The writer API (/api/admin). Function names match the backend route functions.
import { request } from './http'
import type {
  AdminArticle,
  ArticleListItem,
  CreateArticleRequest,
  PublishedArticle,
  SaveDraftRequest,
  Snapshot,
  SnapshotListItem,
} from './types'

const articles = '/admin/articles'

// --- Authoring ---

export function createArticle(body: CreateArticleRequest): Promise<AdminArticle> {
  return request('POST', articles, body)
}

export function listArticles(): Promise<ArticleListItem[]> {
  return request('GET', articles)
}

export function getArticle(articleId: string): Promise<AdminArticle> {
  return request('GET', `${articles}/${articleId}`)
}

export function saveDraft(articleId: string, body: SaveDraftRequest): Promise<AdminArticle> {
  return request('PATCH', `${articles}/${articleId}/draft`, body)
}

// --- Publishing ---

export function publishArticle(
  articleId: string,
  expectedDraftVersion: number,
): Promise<PublishedArticle> {
  return request('POST', `${articles}/${articleId}/publish`, { expectedDraftVersion })
}

export function unpublishArticle(articleId: string): Promise<AdminArticle> {
  return request('POST', `${articles}/${articleId}/unpublish`)
}

// --- History ---

export function listSnapshots(articleId: string): Promise<SnapshotListItem[]> {
  return request('GET', `${articles}/${articleId}/snapshots`)
}

export function getSnapshot(articleId: string, snapshotId: string): Promise<Snapshot> {
  return request('GET', `${articles}/${articleId}/snapshots/${snapshotId}`)
}

export function restoreSnapshot(
  articleId: string,
  snapshotId: string,
  expectedDraftVersion: number,
): Promise<AdminArticle> {
  return request('POST', `${articles}/${articleId}/snapshots/${snapshotId}/restore`, {
    expectedDraftVersion,
  })
}

export function deleteSnapshot(articleId: string, snapshotId: string): Promise<void> {
  return request('DELETE', `${articles}/${articleId}/snapshots/${snapshotId}`)
}
