<script setup lang="ts">
import IconGlobeSvg from '../icons/IconGlobeSvg.vue'
import IconGlobeOffSvg from '../icons/IconGlobeOffSvg.vue'
import IconSaveSvg from '../icons/IconSaveSvg.vue'
import type { EditorAction } from '../../composables/article-editor/useArticleEditor'
import type { ArticleStatus } from '../../services/types'

// Save, Publish, and Unpublish, in one row under the form. While any action runs, every
// control is disabled and the active one shows progress.
defineProps<{
  formId: string
  isNew: boolean
  status: ArticleStatus | null
  isDirty: boolean
  pendingAction: EditorAction | null
}>()

// Save is the editor form's submit button (`formId`), so the browser validates before saving.
const emit = defineEmits<{ publish: []; unpublish: [] }>()
</script>

<template>
  <div class="editor-actions">
    <p v-if="!isNew && isDirty" class="hint">Save your changes before publishing</p>
    <!-- Publishing controls are grouped apart from Save. -->
    <div v-if="!isNew" class="publish-group">
      <button
        v-if="status === 'published'"
        type="button"
        :disabled="pendingAction !== null"
        @click="emit('unpublish')"
      >
        <IconGlobeOffSvg />
        {{ pendingAction === 'unpublish' ? 'Unpublishing…' : 'Unpublish' }}
      </button>
      <button type="button" :disabled="pendingAction !== null || isDirty" @click="emit('publish')">
        <IconGlobeSvg />
        {{ pendingAction === 'publish' ? 'Publishing…' : 'Publish' }}
      </button>
    </div>
    <span v-if="!isNew" class="divider" aria-hidden="true" />
    <button type="submit" :form="formId" class="button-primary" :disabled="pendingAction !== null">
      <IconSaveSvg />
      {{ pendingAction === 'save' ? 'Saving…' : 'Save' }}
    </button>
  </div>
</template>

<style scoped>
.editor-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-4);
  margin-top: var(--space-4);
}

/* A vertical line between the publishing group and Save, as tall as the buttons. */
.divider {
  align-self: stretch;
  width: var(--border-width);
  background: var(--color-border);
}

.publish-group {
  display: flex;
  gap: var(--space-2);
}

/* The hint sits at the left of the row, the buttons at the right. */
.hint {
  margin: var(--space-0) auto var(--space-0) var(--space-0);
  color: var(--color-warning);
  font-size: var(--font-size-sm);
}
</style>
