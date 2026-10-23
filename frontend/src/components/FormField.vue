<script setup lang="ts">
// One form field: a label, the control (default slot), and an optional hint, always spaced
// the same way. A required field gets a marker after its label.
withDefaults(defineProps<{ label: string; for?: string; hint?: string; required?: boolean }>(), {
  for: undefined,
  hint: '',
  required: false,
})
</script>

<template>
  <div class="form-field">
    <label :for="$props.for">
      {{ label }}
      <span v-if="required" class="required" aria-hidden="true">*</span>
    </label>
    <slot />
    <p v-if="hint" class="hint">{{ hint }}</p>
  </div>
</template>

<style scoped>
.required {
  color: var(--color-danger);
}

.hint {
  margin: var(--space-1) var(--space-0) var(--space-0);
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
}
</style>
