<script setup lang="ts">
import { watch } from 'vue'
import AppBreadcrumb from '../components/layout/AppBreadcrumb.vue'
import ErrorBanner from '../components/ErrorBanner.vue'
import MarkdownView from '../components/MarkdownView.vue'
import NotFound from '../components/NotFound.vue'
import TagList from '../components/TagList.vue'
import { usePublicArticles } from '../composables/usePublicArticles'
import { formatDate } from '../lib/format'

const props = defineProps<{ slug: string }>()

const { article, isLoading, error, isNotFound, loadArticle } = usePublicArticles()

watch(
  () => props.slug,
  (slug) => void loadArticle(slug),
  { immediate: true },
)
</script>

<template>
  <p v-if="isLoading" class="muted">Loading…</p>

  <NotFound v-else-if="isNotFound">
    <RouterLink :to="{ name: 'public-list' }">Back to articles</RouterLink>
  </NotFound>

  <ErrorBanner v-else-if="error" :title="error.title" :message="error.message" />

  <article v-else-if="article" class="article">
    <AppBreadcrumb
      :items="[{ label: 'Articles', to: { name: 'public-list' } }, { label: article.title }]"
    />
    <h1>{{ article.title }}</h1>
    <div class="meta">
      <span class="date">{{ formatDate(article.publishedAt) }}</span>
      <TagList :tags="article.tags" />
    </div>
    <MarkdownView class="body" :source="article.body" />
  </article>
</template>

<style scoped>
.muted {
  color: var(--color-text-muted);
}

/* The header and its divider span the content area; the body keeps a comfortable line length. */
.body {
  max-width: var(--reading-width);
}

.meta {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-5);
  padding-bottom: var(--space-4);
  border-bottom: var(--border-width) solid var(--color-border);
}

.date {
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
}
</style>
