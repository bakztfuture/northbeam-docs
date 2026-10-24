<script setup lang="ts">
import IconChevronRightSvg from '../icons/IconChevronRightSvg.vue'
import type { RouteLocationRaw } from 'vue-router'

// Where the page sits: each item but the last links back up; the last is the current page.
defineProps<{ items: { label: string; to?: RouteLocationRaw }[] }>()
</script>

<template>
  <nav class="breadcrumb" aria-label="Breadcrumb">
    <ol>
      <li v-for="(item, index) in items" :key="index">
        <RouterLink v-if="item.to" :to="item.to">{{ item.label }}</RouterLink>
        <span v-else aria-current="page">{{ item.label }}</span>
        <IconChevronRightSvg v-if="index < items.length - 1" class="separator" />
      </li>
    </ol>
  </nav>
</template>

<style scoped>
/* The gap below the breadcrumb is set here only; page titles under it add no top margin. */
.breadcrumb {
  margin-bottom: var(--space-4);
  font-size: var(--font-size-sm);

  & ol {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    margin: var(--space-0);
    padding: var(--space-0);
    list-style: none;
  }

  & li {
    display: inline-flex;
    align-items: center;
    min-width: var(--space-0);
  }

  & a {
    color: var(--color-text-muted);
    font-weight: var(--font-weight-medium);
    text-decoration: none;

    &:hover {
      color: var(--color-primary);
      text-decoration: underline;
    }
  }

  & [aria-current='page'] {
    overflow: hidden;
    max-width: var(--modal-width);
    color: var(--color-text);
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.separator {
  margin-inline: var(--space-1);
  color: var(--color-border);
}
</style>
