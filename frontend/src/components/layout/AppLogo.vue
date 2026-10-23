<script setup lang="ts">
// The Northbeam Docs logo: a north star (its north ray longer, the "beam") on a rounded tile,
// followed by the wordmark. Colors come from tokens; public/favicon.svg is the same mark.
import IconLogoMarkSvg from '../icons/IconLogoMarkSvg.vue'
</script>

<template>
  <span class="logo">
    <IconLogoMarkSvg class="mark" />
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
