<script setup lang="ts">
defineProps<{ tags: string[] }>()
</script>

<template>
  <ul v-if="tags.length" class="tags">
    <li v-for="tag in tags" :key="tag" class="tag">{{ tag }}</li>
  </ul>
</template>

<style scoped>
.tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
  list-style: none;
  margin: var(--space-0);
  padding: var(--space-0);
}

.tag {
  padding: var(--space-0) var(--space-2);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
}
</style>
