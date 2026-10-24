<script setup lang="ts">
import IconPlusSvg from '../components/icons/IconPlusSvg.vue'
import EmptyState from '../components/EmptyState.vue'
import ErrorBanner from '../components/ErrorBanner.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { useArticleList } from '../composables/useArticleList'
import { formatDateTime } from '../lib/format'

const { articles, isLoading, error } = useArticleList()
</script>

<template>
  <header class="page-header">
    <h1>Articles</h1>
    <!-- With no articles, the button moves into the empty state below. -->
    <RouterLink v-if="articles.length" :to="{ name: 'admin-new' }" class="new-article">
      <IconPlusSvg />
      New article
    </RouterLink>
  </header>

  <ErrorBanner v-if="error" :title="error.title" :message="error.message" />

  <p v-if="isLoading" class="muted">Loading…</p>
  <EmptyState
    v-else-if="!error && !articles.length"
    title="No articles yet"
    message="Write your first article. Readers see nothing until you publish it."
  >
    <RouterLink :to="{ name: 'admin-new' }" class="new-article">
      <IconPlusSvg />
      New article</RouterLink
    >
  </EmptyState>
  <table v-else-if="articles.length" class="articles">
    <thead>
      <tr>
        <th>Title</th>
        <th>Slug</th>
        <th>Status</th>
        <th>Updated</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="article in articles" :key="article.id">
        <td>
          <RouterLink :to="{ name: 'admin-editor', params: { id: article.id } }">
            {{ article.title }}
          </RouterLink>
        </td>
        <td class="mono">{{ article.slug }}</td>
        <td><StatusBadge :status="article.status" /></td>
        <td class="mono muted">{{ formatDateTime(article.updatedAt) }}</td>
      </tr>
    </tbody>
  </table>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-4);

  & h1 {
    margin: var(--space-0);
  }
}

.new-article {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-md);
  background: var(--color-primary);
  color: var(--color-text-inverse);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  text-decoration: none;

  &:hover {
    background: var(--color-primary-hover);
    color: var(--color-text-inverse);
  }
}

.muted {
  color: var(--color-text-muted);
}

.articles {
  width: 100%;
  border-collapse: collapse;

  & th,
  & td {
    padding: var(--space-3);
    border-bottom: var(--border-width) solid var(--color-border);
    text-align: left;
  }

  & th {
    color: var(--color-text-muted);
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
  }
}
</style>
