<script setup lang="ts">
import IconCloseSvg from '../icons/IconCloseSvg.vue'
import { formatDateTime } from '../../lib/format'
import type { Snapshot } from '../../services/types'
import MarkdownView from '../MarkdownView.vue'
import ModalShell from '../shared/ModalShell.vue'
import TagList from '../TagList.vue'

// A read-only view of one snapshot. The header stays put; a long body scrolls inside the modal.
defineProps<{ snapshot: Snapshot | null }>()

const emit = defineEmits<{ close: [] }>()
</script>

<template>
  <ModalShell
    :open="snapshot !== null"
    :label="snapshot ? `Snapshot v${snapshot.versionNumber}` : 'Snapshot'"
    size="large"
    @close="emit('close')"
  >
    <template v-if="snapshot">
      <header class="header">
        <div>
          <p class="meta">
            <strong class="mono">v{{ snapshot.versionNumber }}</strong>
            <span v-if="snapshot.isCurrent" class="current">Current</span>
            <span class="mono">{{ formatDateTime(snapshot.createdAt) }}</span>
          </p>
          <h2 class="title">{{ snapshot.title }}</h2>
          <TagList :tags="snapshot.tags" />
        </div>
        <button type="button" class="close" aria-label="Close" @click="emit('close')">
          <IconCloseSvg />
        </button>
      </header>
      <div class="body">
        <MarkdownView :source="snapshot.body" />
      </div>
    </template>
  </ModalShell>
</template>

<style scoped>
.header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  padding-bottom: var(--space-4);
  border-bottom: var(--border-width) solid var(--color-border);
}

.meta {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
  color: var(--color-text-muted);
}

.current {
  color: var(--color-success);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
}

.title {
  margin-bottom: var(--space-2);
  font-size: var(--font-size-2xl);
}

.close {
  flex-shrink: 0;
  padding: var(--space-2);
  border-color: transparent;
}

/* Only the body scrolls, so the header and close button stay in view. */
.body {
  min-height: var(--space-0);
  margin-top: var(--space-4);
  overflow-y: auto;
}
</style>
