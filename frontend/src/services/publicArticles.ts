// The public reader API (/api/public): published content only.
import { request } from './http'
import type { PublicArticle, PublicArticleListItem } from './types'

export function listPublicArticles(): Promise<PublicArticleListItem[]> {
  return request('GET', '/public/articles')
}

export function getPublicArticle(slug: string): Promise<PublicArticle> {
  return request('GET', `/public/articles/${encodeURIComponent(slug)}`)
}
