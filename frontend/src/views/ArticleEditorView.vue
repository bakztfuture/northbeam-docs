<script setup lang="ts">
import { toRef } from 'vue'
import AppBreadcrumb from '../components/layout/AppBreadcrumb.vue'
import ArticleEditorActions from '../components/article-editor/ArticleEditorActions.vue'
import ArticleEditorForm from '../components/article-editor/ArticleEditorForm.vue'
import ArticleEditorHistory from '../components/article-editor/ArticleEditorHistory.vue'
import ArticleEditorSnapshotModal from '../components/article-editor/ArticleEditorSnapshotModal.vue'
import ConfirmModal from '../components/ConfirmModal.vue'
import ErrorBanner from '../components/ErrorBanner.vue'
import NotFound from '../components/NotFound.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { useArticleEditor } from '../composables/article-editor/useArticleEditor'
import { formatDateTime } from '../lib/format'

// Serves both /admin/new (no id: create mode) and /admin/articles/:id.
const props = defineProps<{ id?: string }>()

const {
  saved,
  form,
  isNew,
  isDirty,
  isLoading,
  snapshots,
  visibleSnapshots,
  viewedSnapshot,
  error,
  conflict,
  pendingAction,
  pendingSnapshotId,
  isBusy,
  confirmation,
  confirmPending,
  cancelPending,
  save,
  requestPublish,
  unpublish,
  viewSnapshot,
  closeSnapshot,
  restore,
  removeSnapshot,
  reloadLatest,
} = useArticleEditor(toRef(props, 'id'))
</script>

<template>
  <p v-if="isLoading" class="muted">Loading…</p>

  <NotFound v-else-if="id && !saved && error?.code === 404">
    <RouterLink :to="{ name: 'admin' }">Back to articles</RouterLink>
  </NotFound>

  <ErrorBanner v-else-if="id && !saved && error" :title="error.title" :message="error.message" />

  <template v-else>
    <header class="page-header">
      <div>
        <AppBreadcrumb
          :items="[
            { label: 'Articles', to: { name: 'admin' } },
            { label: isNew ? 'New article' : (saved?.draft.title ?? '') },
          ]"
        />
        <h1>{{ isNew ? 'New article' : saved?.draft.title }}</h1>
        <dl v-if="saved" class="meta">
          <div>
            <dt>Status</dt>
            <dd><StatusBadge :status="saved.status" /></dd>
          </div>
          <div>
            <dt>Draft version</dt>
            <dd>{{ saved.draftVersion }}</dd>
          </div>
          <div>
            <dt>Published</dt>
            <dd>
              {{ saved.publishedAt ? formatDateTime(saved.publishedAt) : 'Never' }}
            </dd>
          </div>
        </dl>
      </div>
    </header>

    <ErrorBanner
      v-if="conflict"
      tone="warning"
      title="This draft changed elsewhere"
      message="Your edits are still here, but they were not saved. Copy anything you want to keep, then reload the latest draft."
    >
      <button type="button" :disabled="isBusy" @click="reloadLatest">
        {{ pendingAction === 'reload' ? 'Reloading…' : 'Reload latest' }}
      </button>
    </ErrorBanner>
    <ErrorBanner v-if="error" :title="error.title" :message="error.message" />

    <div class="grid">
      <div :class="isNew ? 'col-span-12' : 'col-span-8'">
        <ArticleEditorForm
          v-model:title="form.title"
          v-model:tags="form.tags"
          v-model:body="form.body"
          form-id="article-form"
          :slug="saved?.slug ?? null"
          :disabled="isBusy"
          @submit="save"
        />
        <ArticleEditorActions
          form-id="article-form"
          :is-new="isNew"
          :status="saved?.status ?? null"
          :is-dirty="isDirty"
          :pending-action="pendingAction"
          @publish="requestPublish"
          @unpublish="unpublish"
        />
      </div>
      <aside v-if="!isNew" class="col-span-4">
        <ArticleEditorHistory
          :snapshots="visibleSnapshots"
          :total="snapshots.length"
          :pending-action="pendingAction"
          :pending-snapshot-id="pendingSnapshotId"
          @view="viewSnapshot"
          @restore="restore"
          @delete="removeSnapshot"
        />
      </aside>
    </div>

    <ArticleEditorSnapshotModal :snapshot="viewedSnapshot" @close="closeSnapshot" />
    <ConfirmModal v-bind="confirmation" @confirm="confirmPending" @cancel="cancelPending" />
  </template>
</template>

<style scoped>
.page-header {
  margin-bottom: var(--space-5);

  & h1 {
    margin: var(--space-0) var(--space-0) var(--space-2);
  }
}

.meta {
  display: flex;
  gap: var(--space-5);
  margin: var(--space-0);
  font-size: var(--font-size-sm);

  & div {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  & dt {
    color: var(--color-text-muted);
  }

  & dd {
    margin: var(--space-0);
  }
}

.muted {
  color: var(--color-text-muted);
}
</style>
