<script setup lang="ts">
import { onBeforeUnmount, watch } from 'vue'

// The frame every modal shares: a backdrop over the page, a centered dialog, Escape and a
// backdrop click to close, and the fade in and out. What goes inside is up to the caller.
const props = withDefaults(
  defineProps<{ open: boolean; label: string; size?: 'default' | 'large' }>(),
  { size: 'default' },
)

const emit = defineEmits<{ close: [] }>()

// Escape closes, but only while the modal is open.
function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') emit('close')
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
      <div v-if="open" class="backdrop" @click.self="emit('close')">
        <div class="dialog" :class="size" role="dialog" aria-modal="true" :aria-label="label">
          <slot />
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
  padding: var(--space-5);
  background: var(--color-backdrop);
}

.dialog {
  display: flex;
  flex-direction: column;
  width: var(--modal-width);
  max-width: 100%;
  max-height: var(--modal-max-height);
  padding: var(--space-5);
  border-radius: var(--radius-md);
  background: var(--color-bg);
  box-shadow: var(--shadow-modal);

  &.large {
    width: var(--modal-width-lg);
  }
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
</style>
