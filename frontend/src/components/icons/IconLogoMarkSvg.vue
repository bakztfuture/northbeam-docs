<template>
  <!-- The Northbeam north star on a rounded tile; public/favicon.svg is the same mark. -->
  <svg viewBox="0 0 32 32" aria-hidden="true">
    <rect class="tile" width="32" height="32" rx="8" />
    <path class="star" d="M16 4 L18 15 L26 17 L18 19 L16 27 L14 19 L6 17 L14 15 Z" />
  </svg>
</template>

<style scoped>
.tile {
  fill: var(--color-primary);
}

.star {
  fill: var(--color-text-inverse);
}
</style>
