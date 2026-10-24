// Minimal frontend E2E checks (design Decision 7): the app in a real browser, with every /api
// request answered by FakeApi, so no backend or database runs.
import { test as base, expect, type Page } from '@playwright/test'
import { FakeApi } from './fakeApi'

// Each check gets a fresh fake, installed before the page loads (auto, so even a check that
// never touches it is covered); afterwards nothing may have slipped past it toward a real
// backend.
const test = base.extend<{ api: FakeApi }>({
  api: [
    async ({ page }, use) => {
      const api = new FakeApi()
      await api.install(page)
      await use(api)
      expect(api.unhandled).toEqual([])
    },
    { auto: true },
  ],
})

// The body textarea; its tab list shares the "Main content" name, so match the role too.
const bodyField = (page: Page) => page.getByRole('textbox', { name: 'Main content' })
const draftVersion = (page: Page) => page.getByText('Draft version').locator('..')

test('happy path: create, save twice, publish, read, unpublish, not found', async ({ page }) => {
  // Create: nothing is stored until the first save.
  await page.goto('/admin/new')
  await page.getByLabel('Title').fill('Getting started')
  await bodyField(page).fill('# Welcome\n\nFirst version.')
  await page.getByRole('button', { name: 'Save' }).click()

  await expect(page).toHaveURL(/\/admin\/articles\/[^/]+$/)
  const editorUrl = page.url()
  await expect(draftVersion(page)).toContainText('1')

  // Second save: same page, next draft version.
  await bodyField(page).fill('# Welcome\n\nSecond version.')
  await page.getByRole('button', { name: 'Save' }).click()
  await expect(draftVersion(page)).toContainText('2')

  // Publish asks first, then opens the article's public page.
  await page.getByRole('button', { name: 'Publish', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toContainText('Publish this draft?')
  await dialog.getByRole('button', { name: 'Publish' }).click()

  await expect(page).toHaveURL(/\/articles\/[a-z]+$/)
  const publicUrl = page.url()
  await expect(page.getByRole('heading', { name: 'Getting started', level: 1 })).toBeVisible()
  await expect(page.getByText('Second version.')).toBeVisible()

  // Unpublish opens the public list, where the article is gone.
  await page.goto(editorUrl)
  await page.getByRole('button', { name: 'Unpublish' }).click()
  await expect(page).toHaveURL(/\/$/)
  await expect(page.getByText('Check back soon!')).toBeVisible()

  // Its public page now shows the not-found message.
  await page.goto(publicUrl)
  await expect(page.getByRole('heading', { name: 'Not found', level: 1 })).toBeVisible()
})

test('conflict: a stale save shows the banner and Reload latest reloads the draft', async ({
  page,
  api,
}) => {
  const article = api.seedArticle({ title: 'Getting started', body: 'Original body.' })
  await page.goto(`/admin/articles/${article.id}`)
  await expect(bodyField(page)).toHaveValue('Original body.')

  // Another tab saves first, so this page's draft version is now stale.
  api.editElsewhere(article.id, { body: 'Saved in another tab.' })

  await bodyField(page).fill('My local edit.')
  await page.getByRole('button', { name: 'Save' }).click()

  // The conflict is explained and the writer's text is kept.
  const banner = page.getByRole('alert').filter({ hasText: 'This draft changed elsewhere' })
  await expect(banner).toBeVisible()
  await expect(bodyField(page)).toHaveValue('My local edit.')

  // Reload latest loads the other tab's draft straight away, with no confirmation.
  await banner.getByRole('button', { name: 'Reload latest' }).click()
  await expect(page.getByRole('dialog')).toBeHidden()
  await expect(bodyField(page)).toHaveValue('Saved in another tab.')
  await expect(banner).toBeHidden()
  await expect(draftVersion(page)).toContainText('2')
})
