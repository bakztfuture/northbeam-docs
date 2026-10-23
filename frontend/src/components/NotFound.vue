<template>
  <section class="not-found">
    <h1>Not found</h1>
    <p class="message">This page doesn't exist or is no longer available.</p>
    <slot />
  </section>
</template>

<style scoped>
.not-found {
  padding-block: var(--space-7);
  text-align: center;
}

.message {
  color: var(--color-text-muted);
}
</style>
