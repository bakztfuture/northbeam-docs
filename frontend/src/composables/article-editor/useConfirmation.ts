import { reactive } from 'vue'

// The props ConfirmModal is bound to.
export interface Confirmation {
  open: boolean
  title: string
  message: string
  confirmLabel: string
  tone: 'default' | 'danger'
}

// Which confirmation is pending, and what to run if the writer confirms (design Decision 8).
// It knows nothing about articles: the caller passes the text and the action.
export function useConfirmation() {
  const confirmation = reactive<Confirmation>({
    open: false,
    title: '',
    message: '',
    confirmLabel: 'Confirm',
    tone: 'default',
  })
  let pendingRun: (() => Promise<void>) | null = null

  function ask(text: Omit<Confirmation, 'open'>, run: () => Promise<void>) {
    Object.assign(confirmation, text, { open: true })
    pendingRun = run
  }

  // Closing the modal locks nothing; the busy flag is set by the action it runs.
  async function confirmPending() {
    const run = pendingRun
    cancelPending()
    if (run) await run()
  }

  function cancelPending() {
    confirmation.open = false
    pendingRun = null
  }

  return { confirmation, ask, confirmPending, cancelPending }
}
