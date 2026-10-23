<script setup lang="ts">
// The Northbeam Docs logo: a north star (its north ray longer, the "beam") on a rounded tile,
// followed by the wordmark. Colors come from tokens; public/favicon.svg is the same mark.
</script>

<template>
  <span class="logo">
    <svg class="mark" viewBox="0 0 32 32" aria-hidden="true">
      <rect class="tile" width="32" height="32" rx="8" />
      <path class="star" d="M16 4 L18 15 L26 17 L18 19 L16 27 L14 19 L6 17 L14 15 Z" />
    </svg>
    <span class="wordmark">Northbeam <span class="product">Docs</span></span>
  </span>
</template>

<style scoped>
.logo {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
}

.mark {
  width: var(--logo-size);
  height: var(--logo-size);
}

.tile {
  fill: var(--color-primary);
}

.star {
  fill: var(--color-text-inverse);
}

.wordmark {
  color: var(--color-text);
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-bold);
  letter-spacing: var(--letter-spacing-tight);
}

.product {
  color: var(--color-primary);
  font-weight: var(--font-weight-medium);
}
</style>
