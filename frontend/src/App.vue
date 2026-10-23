<script setup lang="ts">
import AppFooter from './components/layout/AppFooter.vue'
import AppNavbar from './components/layout/AppNavbar.vue'
</script>

<template>
  <!-- The footer sits at the bottom of the window on short pages and after the content on long
       ones; the main area's bottom padding keeps a gap above it. -->
  <div class="layout">
    <AppNavbar />
    <main class="container main">
      <RouterView />
    </main>
    <AppFooter />
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.main {
  flex: 1;
  width: 100%;
  padding-top: var(--space-6);
  padding-bottom: var(--page-bottom-gap);
}
</style>
