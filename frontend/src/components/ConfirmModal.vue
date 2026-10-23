<script setup lang="ts">
import { onBeforeUnmount, watch } from 'vue'

const props = withDefaults(
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

// Escape cancels, but only while the modal is open.
function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') emit('cancel')
}

watch(
  () => props.open,
  (open) => {
    if (open) window.addEventListener('keydown', onKeydown)
    else window.removeEventListener('keydown', onKeydown)
  },
  { immediate: true },
)

onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="open" class="backdrop" @click.self="emit('cancel')">
        <div class="dialog" role="dialog" aria-modal="true" :aria-label="title">
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
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.backdrop {
  position: fixed;
  inset: var(--space-0);
  z-index: var(--z-modal);
  display: grid;
  place-items: center;
  background: var(--color-backdrop);
}

.dialog {
  width: var(--modal-width);
  padding: var(--space-5);
  border-radius: var(--radius-md);
  background: var(--color-bg);
  box-shadow: var(--shadow-modal);
}

/* Fade the backdrop and let the dialog rise slightly as it appears; reversed on close. */
.modal-enter-active,
.modal-leave-active {
  transition: opacity var(--duration-fast) var(--easing-standard);

  & .dialog {
    transition: transform var(--duration-fast) var(--easing-standard);
  }
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;

  & .dialog {
    transform: translateY(var(--space-2)) scale(0.98);
  }
}

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
