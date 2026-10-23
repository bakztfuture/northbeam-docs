import { ref } from 'vue'
import type { ApiError } from '../services/http'
import { listArticles } from '../services/adminArticles'
import type { ArticleListItem } from '../services/types'
import { toApiError } from './errors'

// The writer's article list: every article, newest updatedAt first (the API's order).
export function useArticleList() {
  const articles = ref<ArticleListItem[]>([])
  const isLoading = ref(false)
  const error = ref<ApiError | null>(null)

  async function load() {
    isLoading.value = true
    error.value = null
    try {
      articles.value = await listArticles()
    } catch (e) {
      error.value = toApiError(e)
    } finally {
      isLoading.value = false
    }
  }

  void load()

  return { articles, isLoading, error, load }
}
