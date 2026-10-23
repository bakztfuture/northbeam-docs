<script setup lang="ts">
import IconEyeSvg from '../icons/IconEyeSvg.vue'
import IconTrashSvg from '../icons/IconTrashSvg.vue'
import IconUndoSvg from '../icons/IconUndoSvg.vue'
import type { EditorAction } from '../../composables/article-editor/useArticleEditor'
import { formatDateTime } from '../../lib/format'
import type { SnapshotListItem } from '../../services/types'

// The article's most recent snapshots, newest first; `total` counts all of them. The snapshot
// the article points to is marked and cannot be deleted.
defineProps<{
  snapshots: SnapshotListItem[]
  total: number
  pendingAction: EditorAction | null
  pendingSnapshotId: string | null
}>()

const emit = defineEmits<{
  view: [snapshotId: string]
  restore: [snapshotId: string]
  delete: [snapshotId: string]
}>()
</script>

<template>
  <section class="history">
    <h2 class="heading">History</h2>
    <p v-if="!snapshots.length" class="hint">No snapshots yet. Each publish adds one.</p>
    <p v-if="total > snapshots.length" class="hint limit">
      Showing the {{ snapshots.length }} most recent of {{ total }}
    </p>
    <ol v-if="snapshots.length" class="list">
      <li v-for="snapshot in snapshots" :key="snapshot.id" class="item">
        <div class="summary">
          <strong class="mono">v{{ snapshot.versionNumber }}</strong>
          <span v-if="snapshot.isCurrent" class="current">Current</span>
          <span class="time mono">{{ formatDateTime(snapshot.createdAt) }}</span>
        </div>
        <p class="title">{{ snapshot.title }}</p>
        <div class="actions">
          <button type="button" @click="emit('view', snapshot.id)">
            <IconEyeSvg />
            View
          </button>
          <button
            type="button"
            :disabled="pendingAction !== null"
            @click="emit('restore', snapshot.id)"
          >
            <IconUndoSvg />
            {{
              pendingAction === 'restore' && pendingSnapshotId === snapshot.id
                ? 'Restoring…'
                : 'Restore'
            }}
          </button>
          <button
            v-if="!snapshot.isCurrent"
            type="button"
            :disabled="pendingAction !== null"
            @click="emit('delete', snapshot.id)"
          >
            <IconTrashSvg />
            {{
              pendingAction === 'delete' && pendingSnapshotId === snapshot.id
                ? 'Deleting…'
                : 'Delete'
            }}
          </button>
        </div>
        <p v-if="snapshot.isCurrent" class="hint">
          Can't be deleted while it is the article's current or last published version.
        </p>
      </li>
    </ol>
  </section>
</template>

<style scoped>
.history {
  padding: var(--space-4);
  border: var(--border-width) solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
}

.heading {
  font-size: var(--font-size-lg);
}

.hint {
  margin: var(--space-1) var(--space-0) var(--space-0);
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
}

.limit {
  margin-bottom: var(--space-3);
}

.list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  list-style: none;
  margin: var(--space-0);
  padding: var(--space-0);
}

.item {
  padding: var(--space-3);
  border: var(--border-width) solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg);
}

.summary {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
}

.current {
  color: var(--color-success);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
}

.time {
  margin-left: auto;
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
}

.title {
  margin: var(--space-1) var(--space-0) var(--space-2);
  font-size: var(--font-size-sm);
}

.actions {
  display: flex;
  gap: var(--space-2);

  & button {
    gap: var(--space-1);
    padding: var(--space-1) var(--space-3);
    font-size: var(--font-size-xs);
  }

  & .icon {
    width: var(--icon-size-sm);
    height: var(--icon-size-sm);
  }
}
</style>
