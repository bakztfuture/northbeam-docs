<script setup lang="ts">
// The brand footer on every page. The year follows the clock, so it never needs updating.
const year = new Date().getFullYear()
</script>

<template>
  <footer class="footer">
    <p class="container copyright">&copy; {{ year }} Northbeam. All rights reserved.</p>
  </footer>
</template>

<style scoped>
.footer {
  padding-block: var(--space-7);
  border-top: var(--border-width) solid var(--color-border);
  background: var(--color-surface);
}

.copyright {
  margin-block: var(--space-0);
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
  text-align: center;
}
</style>
