<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppLogo from './AppLogo.vue'

// Highlight the section, not just the exact route: a public article keeps "Public" selected,
// and the editor keeps "Admin" selected.
const route = useRoute()
const section = computed(() => (String(route.name ?? '').startsWith('admin') ? 'admin' : 'public'))
</script>

<template>
  <header class="header">
    <nav class="container nav">
      <RouterLink :to="{ name: 'public-list' }" class="brand" aria-label="Northbeam Docs home">
        <AppLogo />
      </RouterLink>
      <div class="links">
        <RouterLink :to="{ name: 'public-list' }" :class="{ active: section === 'public' }">
          <svg
            class="icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <circle cx="12" cy="12" r="10" />
            <path d="M2 12h20" />
            <path
              d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"
            />
          </svg>
          Public
        </RouterLink>
        <RouterLink :to="{ name: 'admin' }" :class="{ active: section === 'admin' }">
          <svg
            class="icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <circle cx="12" cy="12" r="3" />
            <path
              d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"
            />
          </svg>
          Admin
        </RouterLink>
      </div>
    </nav>
  </header>
</template>

<style scoped>
.header {
  border-bottom: var(--border-width) solid var(--color-border);
  background: var(--color-surface);
}

.nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-block: var(--space-3);
}

.brand {
  text-decoration: none;
}

.links {
  display: flex;
  gap: var(--space-2);

  & a {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    padding: var(--space-2) var(--space-4);
    border: var(--border-width) solid transparent;
    border-radius: var(--radius-md);
    color: var(--color-text-muted);
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    text-decoration: none;

    &:hover {
      color: var(--color-text);
      background: var(--color-bg);
    }

    &.active {
      border-color: var(--color-primary);
      background: var(--color-bg);
      color: var(--color-primary);
      font-weight: var(--font-weight-semibold);
    }
  }
}

.icon {
  width: var(--icon-size);
  height: var(--icon-size);
}
</style>
