<script setup lang="ts">
import IconChevronRightSvg from '../components/icons/IconChevronRightSvg.vue'
import IconFileTextSvg from '../components/icons/IconFileTextSvg.vue'
import EmptyState from '../components/EmptyState.vue'
import ErrorBanner from '../components/ErrorBanner.vue'
import TagList from '../components/TagList.vue'
import { usePublicArticles } from '../composables/usePublicArticles'
import { formatDate } from '../lib/format'

const { articles, isLoading, error, loadList } = usePublicArticles()
void loadList()
</script>

<template>
  <h1 class="page-title">Articles</h1>

  <ErrorBanner v-if="error" :title="error.title" :message="error.message" />

  <p v-if="isLoading" class="muted">Loading…</p>
  <EmptyState
    v-else-if="!error && !articles.length"
    illustration="clock"
    title="Check back soon!"
    message="New articles appear here as soon as they are published."
  />
  <ul v-else-if="articles.length" class="articles">
    <li v-for="article in articles" :key="article.slug">
      <!-- The whole card is one link to the article. -->
      <RouterLink :to="{ name: 'public-article', params: { slug: article.slug } }" class="article">
        <div class="page-icon">
          <IconFileTextSvg />
        </div>
        <div class="content">
          <span class="title">{{ article.title }}</span>
          <span class="date">{{ formatDate(article.publishedAt) }}</span>
          <TagList :tags="article.tags" />
        </div>
        <IconChevronRightSvg class="chevron" />
      </RouterLink>
    </li>
  </ul>
</template>

<style scoped>
/* Matches the admin list's header spacing. */
.page-title {
  margin-bottom: var(--space-4);
}

.muted {
  color: var(--color-text-muted);
}

.articles {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  list-style: none;
  margin: var(--space-0);
  padding: var(--space-0);
}

.article {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-5) var(--space-6);
  border: var(--border-width) solid var(--color-border);
  border-radius: var(--radius-md);
  color: var(--color-text);
  text-decoration: none;

  &:hover {
    border-color: var(--color-primary);
    color: var(--color-text);

    & .title {
      color: var(--color-primary);
    }

    & .chevron {
      color: var(--color-text);
    }
  }
}

.page-icon {
  display: grid;
  flex-shrink: 0;
  place-items: center;
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  color: var(--color-primary);

  & .icon {
    width: var(--icon-size-lg);
    height: var(--icon-size-lg);
  }
}

.content {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: var(--space-1);
  min-width: var(--space-0);
}

.title {
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-semibold);
  line-height: var(--line-height-tight);
}

.date {
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
}

.chevron {
  width: var(--icon-size-lg);
  height: var(--icon-size-lg);
  color: var(--color-text-muted);
}
</style>
