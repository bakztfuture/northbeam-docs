<script setup lang="ts">
import IllustrationClockSvg from './illustrations/IllustrationClockSvg.vue'
import IllustrationPagesSvg from './illustrations/IllustrationPagesSvg.vue'

// A centered box for a page with nothing to show yet: an illustration, a title, a message,
// and an action passed in through the default slot.
withDefaults(defineProps<{ title: string; message: string; illustration?: 'pages' | 'clock' }>(), {
  illustration: 'pages',
})
</script>

<template>
  <section class="empty-state">
    <IllustrationPagesSvg v-if="illustration === 'pages'" class="illustration" />
    <IllustrationClockSvg v-else class="illustration" />
    <h2 class="title">{{ title }}</h2>
    <p class="message">{{ message }}</p>
    <slot />
  </section>
</template>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--space-8) var(--space-5);
  border: var(--border-width) dashed var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  text-align: center;
}

/* Size and spacing only; each illustration colors itself. */
.illustration {
  width: var(--illustration-size);
  margin-bottom: var(--space-4);
}

.title {
  margin-bottom: var(--space-2);
  font-size: var(--font-size-xl);
}

.message {
  max-width: var(--modal-width);
  margin-bottom: var(--space-5);
  color: var(--color-text-muted);
  text-wrap: balance;

  /* With no action below, keep the box's top and bottom padding even. */
  &:last-child {
    margin-bottom: var(--space-0);
  }
}
</style>
