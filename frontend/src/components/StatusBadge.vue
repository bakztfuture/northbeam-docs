<script setup lang="ts">
import type { ArticleStatus } from '../services/types'

defineProps<{ status: ArticleStatus }>()
</script>

<template>
  <span class="badge" :class="status">{{ status }}</span>
</template>

<style scoped>
.badge {
  display: inline-block;
  padding: var(--space-0) var(--space-2);
  border: var(--border-width) solid currentColor;
  border-radius: var(--radius-sm);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  line-height: var(--line-height-normal);

  &.draft {
    color: var(--color-status-draft);
  }

  &.published {
    color: var(--color-status-published);
  }

  &.unpublished {
    color: var(--color-status-unpublished);
  }
}
</style>
