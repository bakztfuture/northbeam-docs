import { computed, ref, watch, type Ref } from 'vue'
import { useRouter } from 'vue-router'
import { parseTags } from '../../lib/fieldValidation'
import { randomSlug } from '../../lib/slug'
import { ApiError } from '../../services/http'
import {
  createArticle,
  deleteSnapshot,
  getArticle,
  getSnapshot,
  listSnapshots,
  publishArticle,
  restoreSnapshot,
  saveDraft,
  unpublishArticle,
} from '../../services/adminArticles'
import type { AdminArticle, Snapshot, SnapshotListItem } from '../../services/types'
import { toApiError } from '../errors'
import { formsDiffer, starterForm, toForm, type ArticleFormFields } from './form'
import { useConfirmation } from './useConfirmation'

// The history panel shows only the newest snapshots; the API still returns every one.
const HISTORY_LIMIT = 10

export type EditorAction = 'save' | 'publish' | 'unpublish' | 'restore' | 'delete' | 'reload'

// Everything on the editor page (design Decision 8). `id` is the route's article id, or
// undefined on /admin/new. The view is reused when the route changes (for example after the
// first save), so the editor follows `id` rather than reading it once.
export function useArticleEditor(id: Ref<string | undefined>) {
  const router = useRouter()

  // The last draft the API returned, and what is in the inputs.
  const saved = ref<AdminArticle | null>(null)
  const form = ref<ArticleFormFields>({ ...starterForm })
  // The slug the first save will send; replaced after a 409 "Slug already exists".
  let newSlug = randomSlug()

  const snapshots = ref<SnapshotListItem[]>([])
  // The pointed-to snapshot is always the newest, so it is always among these.
  const visibleSnapshots = computed(() => snapshots.value.slice(0, HISTORY_LIMIT))
  const viewedSnapshot = ref<Snapshot | null>(null)

  const isLoading = ref(false)
  const error = ref<ApiError | null>(null)
  const conflict = ref<ApiError | null>(null)

  // One action at a time: set just before a request is sent, cleared in `finally`.
  const pendingAction = ref<EditorAction | null>(null)
  const pendingSnapshotId = ref<string | null>(null)
  const isBusy = computed(() => pendingAction.value !== null)

  const isNew = computed(() => saved.value === null)

  const isDirty = computed(() =>
    formsDiffer(form.value, saved.value ? toForm(saved.value) : starterForm),
  )

  // --- Confirmation ---

  const { confirmation, ask, confirmPending, cancelPending } = useConfirmation()

  // --- Running an action ---

  // A 409 from save, publish, or restore means the draft changed elsewhere: show the conflict
  // banner and keep the form. Any other error is shown as a page-level error.
  async function run(
    action: EditorAction,
    request: () => Promise<void>,
    options: { conflictOn409?: boolean; snapshotId?: string } = {},
  ) {
    pendingAction.value = action
    pendingSnapshotId.value = options.snapshotId ?? null
    error.value = null
    try {
      await request()
    } catch (e) {
      const apiError = toApiError(e)
      if (options.conflictOn409 && apiError.code === 409) conflict.value = apiError
      else error.value = apiError
    } finally {
      pendingAction.value = null
      pendingSnapshotId.value = null
    }
  }

  // Replace both copies, so normalized tags (for example "API" stored as "api") do not leave
  // the editor looking dirty.
  function applyArticle(article: AdminArticle) {
    saved.value = article
    form.value = toForm(article)
  }

  async function reloadSnapshots(articleId: string) {
    snapshots.value = await listSnapshots(articleId)
  }

  function requireSaved(): AdminArticle {
    if (!saved.value) throw new Error('This action needs a saved article')
    return saved.value
  }

  // --- Loading ---

  async function load(articleId: string) {
    isLoading.value = true
    error.value = null
    try {
      const [article, list] = await Promise.all([getArticle(articleId), listSnapshots(articleId)])
      applyArticle(article)
      snapshots.value = list
    } catch (e) {
      error.value = toApiError(e)
    } finally {
      isLoading.value = false
    }
  }

  function reset() {
    saved.value = null
    form.value = { ...starterForm }
    newSlug = randomSlug()
    snapshots.value = []
    viewedSnapshot.value = null
    error.value = null
    conflict.value = null
    cancelPending()
  }

  watch(
    id,
    (articleId) => {
      // After the first save the route gains the id of the article already loaded.
      if (articleId && articleId === saved.value?.id) return
      reset()
      if (articleId) void load(articleId)
    },
    { immediate: true },
  )

  // --- Save ---

  // POST on the first save, then PATCH with the loaded draft version.
  async function save() {
    const { title, body, tags } = form.value
    if (isNew.value) {
      await run('save', async () => {
        let article: AdminArticle
        try {
          article = await createArticle({ title, slug: newSlug, body, tags: parseTags(tags) })
        } catch (e) {
          // The error is still shown; the next save tries a fresh slug.
          if (e instanceof ApiError && e.code === 409) newSlug = randomSlug()
          throw e
        }
        applyArticle(article)
        await router.replace({ name: 'admin-editor', params: { id: article.id } })
      })
      return
    }
    const article = requireSaved()
    await run(
      'save',
      async () => {
        applyArticle(
          await saveDraft(article.id, {
            title,
            body,
            tags: parseTags(tags),
            expectedDraftVersion: article.draftVersion,
          }),
        )
      },
      { conflictOn409: true },
    )
  }

  // --- Publish and unpublish ---

  function requestPublish() {
    ask(
      {
        title: 'Publish this draft?',
        message: 'Readers will see it immediately.',
        confirmLabel: 'Publish',
        tone: 'default',
      },
      publish,
    )
  }

  async function publish() {
    const article = requireSaved()
    await run(
      'publish',
      async () => {
        const result = await publishArticle(article.id, article.draftVersion)
        // Show the writer what readers now see. The editor reloads fresh if they come back.
        await router.push({ name: 'public-article', params: { slug: result.article.slug } })
      },
      { conflictOn409: true },
    )
  }

  async function unpublish() {
    const article = requireSaved()
    await run('unpublish', async () => {
      await unpublishArticle(article.id)
      // The public list, where the article no longer appears.
      await router.push({ name: 'public-list' })
    })
  }

  // --- History ---

  async function viewSnapshot(snapshotId: string) {
    const article = requireSaved()
    error.value = null
    try {
      viewedSnapshot.value = await getSnapshot(article.id, snapshotId)
    } catch (e) {
      error.value = toApiError(e)
    }
  }

  function closeSnapshot() {
    viewedSnapshot.value = null
  }

  async function restore(snapshotId: string) {
    const article = requireSaved()
    await run(
      'restore',
      async () => {
        applyArticle(await restoreSnapshot(article.id, snapshotId, article.draftVersion))
      },
      { conflictOn409: true, snapshotId },
    )
  }

  async function removeSnapshot(snapshotId: string) {
    const article = requireSaved()
    await run(
      'delete',
      async () => {
        await deleteSnapshot(article.id, snapshotId)
        if (viewedSnapshot.value?.id === snapshotId) viewedSnapshot.value = null
        await reloadSnapshots(article.id)
      },
      { snapshotId },
    )
  }

  // --- Conflicts ---

  // Conflict banner shown, reload the page to sync with db
  async function reloadLatest() {
    const article = requireSaved()
    await run('reload', async () => {
      const [latest, list] = await Promise.all([getArticle(article.id), listSnapshots(article.id)])
      applyArticle(latest)
      snapshots.value = list
      conflict.value = null
    })
  }

  return {
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
  }
}
