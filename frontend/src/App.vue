<script setup lang="ts">
import AppNavbar from './components/AppNavbar.vue'
</script>

<template>
  <AppNavbar />
  <main class="container main">
    <RouterView />
  </main>
</template>

<style scoped>
.main {
  padding-block: var(--space-6);
}
</style>
