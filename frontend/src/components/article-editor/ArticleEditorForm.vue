<script setup lang="ts">
import { nextTick, onMounted, ref, watch, watchEffect } from 'vue'
import { BODY_MAX, TITLE_MAX, blankProblem, tagsProblem } from '../../lib/fieldValidation'
import FormField from '../FormField.vue'
import MarkdownView from '../MarkdownView.vue'

// The editor's inputs in one card: title (and slug), the body (with a Preview tab), then tags.
// The preview renders the unsaved body in the browser and sends nothing.
// `slug` is shown read-only once the article exists; the new form has no slug field.
// Save submits this form (its button sits outside, linked by `formId`), so the browser checks
// the fields first and nothing is sent until they pass.
defineProps<{ formId: string; slug: string | null; disabled: boolean }>()

const emit = defineEmits<{ submit: [] }>()

// One model per field, so each input updates only its own value.
const title = defineModel<string>('title', { required: true })
const tags = defineModel<string>('tags', { required: true })
const body = defineModel<string>('body', { required: true })

const tab = ref<'body' | 'preview'>('body')

// The body grows with its content instead of scrolling inside a fixed box. It is refitted
// after every change, including a restore or reload that replaces the text, and when the Body
// tab comes back.
const bodyInput = ref<HTMLTextAreaElement | null>(null)

function autoGrowTextArea() {
  const el = bodyInput.value
  if (!el) return
  el.style.height = 'auto'
  // scrollHeight leaves out the border, which the border-box height includes.
  el.style.height = `${el.scrollHeight + el.offsetHeight - el.clientHeight}px`
}

watch([body, tab], () => nextTick(autoGrowTextArea))
onMounted(autoGrowTextArea)

// --- Validation ---

// `required` and `maxlength` are on the inputs; these add what the browser cannot express:
// whitespace-only text, and the tag count and length.
const formEl = ref<HTMLFormElement | null>(null)
const titleInput = ref<HTMLInputElement | null>(null)
const tagsInput = ref<HTMLInputElement | null>(null)

watchEffect(() => {
  titleInput.value?.setCustomValidity(blankProblem(title.value, 'The title'))
  bodyInput.value?.setCustomValidity(blankProblem(body.value, 'The main content'))
  tagsInput.value?.setCustomValidity(tagsProblem(tags.value))
})

// The body is hidden while Preview is open, and the browser cannot point at a hidden field, so
// an invalid body brings its tab back and then shows the message.
function onInvalid(event: Event) {
  if (event.target === bodyInput.value && tab.value === 'preview') {
    tab.value = 'body'
    void nextTick(() => formEl.value?.reportValidity())
  }
}
</script>

<template>
  <form
    :id="formId"
    ref="formEl"
    class="card"
    @submit.prevent="emit('submit')"
    @invalid.capture="onInvalid"
  >
    <fieldset class="fields" :disabled="disabled">
      <div class="grid">
        <FormField
          :class="slug === null ? 'col-span-12' : 'col-span-6'"
          label="Title"
          for="article-title"
          hint="Up to 200 characters."
          required
        >
          <input
            id="article-title"
            ref="titleInput"
            v-model="title"
            required
            :maxlength="TITLE_MAX"
          />
        </FormField>
        <FormField
          v-if="slug !== null"
          class="col-span-6"
          label="Slug"
          for="article-slug"
          hint="Generated automatically and fixed once the article exists."
        >
          <input id="article-slug" class="mono" :value="slug" readonly />
        </FormField>
        <FormField
          class="col-span-12"
          label="Main content"
          for="article-body"
          hint="Markdown: headings, bold, italic, lists, links, quotes, and code."
          required
        >
          <div class="tabs" role="tablist" aria-label="Main content">
            <button
              type="button"
              role="tab"
              class="tab"
              :class="{ active: tab === 'body' }"
              :aria-selected="tab === 'body'"
              @click="tab = 'body'"
            >
              Body
            </button>
            <button
              type="button"
              role="tab"
              class="tab"
              :class="{ active: tab === 'preview' }"
              :aria-selected="tab === 'preview'"
              @click="tab = 'preview'"
            >
              Preview
            </button>
          </div>
          <textarea
            v-show="tab === 'body'"
            id="article-body"
            ref="bodyInput"
            v-model="body"
            class="panel"
            required
            :maxlength="BODY_MAX"
          />
          <div v-if="tab === 'preview'" class="panel preview" role="tabpanel">
            <MarkdownView v-if="body.trim()" :source="body" />
            <p v-else class="empty">Nothing to preview yet.</p>
          </div>
        </FormField>
        <FormField
          class="col-span-12"
          label="Tags"
          for="article-tags"
          hint="Optional. Comma-separated, for example: billing, api"
        >
          <input id="article-tags" ref="tagsInput" v-model="tags" />
        </FormField>
      </div>
      <p class="legend"><span class="required">*</span> Required</p>
    </fieldset>
  </form>
</template>

<style scoped>
.fields {
  margin: var(--space-0);
  padding: var(--space-0);
  border: none;
}

.card {
  padding: var(--space-5);
  border: var(--border-width) solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg);
}

.tabs {
  display: flex;
  gap: var(--space-1);
  border-bottom: var(--border-width) solid var(--color-border);
}

/* Tabs are the one button style that is not a box: a label with an underline when active. */
.tab {
  margin-bottom: calc(-1 * var(--border-width));
  padding: var(--space-2) var(--space-3);
  border: none;
  border-bottom: var(--border-width-thick) solid transparent;
  border-radius: var(--space-0);
  background: none;
  color: var(--color-text-muted);

  &:hover:not(:disabled) {
    background: none;
    color: var(--color-text);
  }

  &.active {
    border-bottom-color: var(--color-primary);
    color: var(--color-primary);
  }
}

/* Body and preview start at the same height, so switching tabs does not move the page. */
.panel {
  display: block;
  min-height: var(--editor-height);
  margin-top: var(--space-3);
}

/* The body sizes itself to its content (autoGrowTextArea), so it neither scrolls nor needs a
   handle. */
textarea.panel {
  overflow: hidden;
  resize: none;
}

.preview {
  padding: var(--space-3) var(--space-4);
  border: var(--border-width) dashed var(--color-border);
  border-radius: var(--radius-md);
}

.empty {
  color: var(--color-text-muted);
}

.required {
  color: var(--color-danger);
}

.legend {
  margin: var(--space-4) var(--space-0) var(--space-0);
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
}
</style>
