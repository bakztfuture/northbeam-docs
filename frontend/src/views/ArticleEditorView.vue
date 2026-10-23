<script setup lang="ts">
// Serves both /admin/new (no id: create mode) and /admin/articles/:id.
defineProps<{ id?: string }>()
</script>

<template>
  <!-- Placeholder: the real page arrives with the writer and public UI (group 5). -->
  <h1>{{ id ? 'Edit article' : 'New article' }}</h1>
</template>
