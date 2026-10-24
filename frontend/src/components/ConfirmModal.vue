<script setup lang="ts">
import ModalShell from './shared/ModalShell.vue'

// One confirmation for every action that asks first, driven entirely by props.
withDefaults(
  defineProps<{
    open: boolean
    title: string
    message: string
    confirmLabel?: string
    cancelLabel?: string
    tone?: 'default' | 'danger'
  }>(),
  { confirmLabel: 'Confirm', cancelLabel: 'Cancel', tone: 'default' },
)

const emit = defineEmits<{ confirm: []; cancel: [] }>()
</script>

<template>
  <!-- Escape and a backdrop click close the shell, which counts as cancelling. -->
  <ModalShell :open="open" :label="title" @close="emit('cancel')">
    <h2 class="title">{{ title }}</h2>
    <p class="message">{{ message }}</p>
    <div class="actions">
      <button type="button" @click="emit('cancel')">{{ cancelLabel }}</button>
      <button
        type="button"
        :class="tone === 'danger' ? 'button-danger' : 'button-primary'"
        @click="emit('confirm')"
      >
        {{ confirmLabel }}
      </button>
    </div>
  </ModalShell>
</template>

<style scoped>
.title {
  font-size: var(--font-size-xl);
}

.message {
  color: var(--color-text-muted);
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
}
</style>
