<script setup lang="ts">
import IconGearSvg from '../icons/IconGearSvg.vue'
import IconGlobeSvg from '../icons/IconGlobeSvg.vue'
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
          <IconGlobeSvg />
          Public
        </RouterLink>
        <RouterLink :to="{ name: 'admin' }" :class="{ active: section === 'admin' }">
          <IconGearSvg />
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
