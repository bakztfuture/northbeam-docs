import { computed, ref } from 'vue'
import type { ApiError } from '../services/http'
import { getPublicArticle, listPublicArticles } from '../services/publicArticles'
import type { PublicArticle, PublicArticleListItem } from '../services/types'
import { toApiError } from './errors'

// The public list and the public article by slug. Both read only published snapshots.
export function usePublicArticles() {
  const articles = ref<PublicArticleListItem[]>([])
  const article = ref<PublicArticle | null>(null)
  const isLoading = ref(false)
  const error = ref<ApiError | null>(null)

  // The API answers draft-only, unpublished, and unknown slugs with the same 404.
  const isNotFound = computed(() => error.value?.code === 404)

  async function loadList() {
    await track(async () => {
      articles.value = await listPublicArticles()
    })
  }

  async function loadArticle(slug: string) {
    article.value = null
    await track(async () => {
      article.value = await getPublicArticle(slug)
    })
  }

  async function track(fetch: () => Promise<void>) {
    isLoading.value = true
    error.value = null
    try {
      await fetch()
    } catch (e) {
      error.value = toApiError(e)
    } finally {
      isLoading.value = false
    }
  }

  return { articles, article, isLoading, error, isNotFound, loadList, loadArticle }
}
