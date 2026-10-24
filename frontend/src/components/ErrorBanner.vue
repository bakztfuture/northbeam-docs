<script setup lang="ts">
// A page-level error: shows the API's title and message. It never retries; any action
// (such as "Reload latest" after a conflict) is passed in through the default slot.
withDefaults(defineProps<{ title: string; message?: string; tone?: 'danger' | 'warning' }>(), {
  message: '',
  tone: 'danger',
})
</script>

<template>
  <div class="banner" :class="tone" role="alert">
    <div>
      <strong>{{ title }}</strong>
      <p v-if="message" class="message">{{ message }}</p>
    </div>
    <div v-if="$slots.default" class="actions">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-5);
  padding: var(--space-3) var(--space-4);
  border: var(--border-width) solid;
  border-radius: var(--radius-md);

  &.danger {
    border-color: var(--color-danger);
    background: var(--color-danger-surface);
  }

  &.warning {
    border-color: var(--color-warning);
    background: var(--color-warning-surface);
  }
}

.message {
  margin: var(--space-1) var(--space-0) var(--space-0);
}

.actions {
  display: flex;
  gap: var(--space-2);
}
</style>
