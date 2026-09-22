import { AUTH_PERSONAS, loginThroughUi } from './auth-personas'
import { expect, test, type Page } from './fixtures'

// English interface: dev/development-plan/24-i18n.md, docs/i18n.md.
// The account language is saved from the personal cabinet (Staff: header menu),
// the page reloads in it, and a new device picks it up at sign-in. Fixture
// accounts are shared by all specs, so every test restores Russian.

async function saveAccountLocale(page: Page, audience: string, locale: 'ru' | 'en') {
  const status = await page.evaluate(
    async ({ audience, locale }) =>
      (
        await fetch(`/${audience}/api/v1/auth/locale`, {
          method: 'PUT',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ locale }),
        })
      ).status,
    { audience, locale },
  )
  expect(status).toBe(200)
}

test('Student switches the account to English in the profile', async ({ page, browser }) => {
  await loginThroughUi(page, AUTH_PERSONAS.student, '/student/profile')
  try {
    await page.getByRole('radio', { name: 'English' }).click()
    await expect(page.locator('html')).toHaveAttribute('lang', 'en')
    await expect(page.getByRole('link', { name: 'Problems' }).first()).toBeVisible()
    await expect(page.getByText('Interface language').first()).toBeVisible()

    await page.reload()
    await expect(page.getByRole('link', { name: 'Profile' }).first()).toBeVisible()

    // A second device gets the account language right after sign-in.
    const otherDevice = await browser.newContext()
    const otherPage = await otherDevice.newPage()
    await loginThroughUi(otherPage, AUTH_PERSONAS.student, '/student/')
    await expect(otherPage.locator('html')).toHaveAttribute('lang', 'en')
    await otherDevice.close()
  } finally {
    await saveAccountLocale(page, 'student', 'ru')
  }
})

test('Staff switches the language from the header menu', async ({ page }) => {
  await loginThroughUi(page, AUTH_PERSONAS.admin, '/staff/')
  try {
    await page.getByRole('button', { name: 'Язык интерфейса' }).click()
    await page.getByRole('menuitem', { name: 'English' }).click()
    await expect(page.locator('html')).toHaveAttribute('lang', 'en')
    await expect(page.getByRole('button', { name: 'Interface language' })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Overview' }).first()).toBeVisible()
  } finally {
    await saveAccountLocale(page, 'staff', 'ru')
  }
})

test('English device language translates the sign-in page', async ({ page, context, baseURL }) => {
  await context.addCookies([{ name: 'vmsh-locale', value: 'en', url: baseURL ?? '' }])
  await page.goto('/family/login')
  await expect(page.locator('html')).toHaveAttribute('lang', 'en')
  await expect(page.getByRole('button', { name: 'Sign in' })).toBeVisible()
  await expect(page.getByLabel('Password', { exact: true })).toBeVisible()
})

test('Russian stays the default without a device choice', async ({ page }) => {
  await loginThroughUi(page, AUTH_PERSONAS.student, '/student/profile')
  await expect(page.locator('html')).toHaveAttribute('lang', 'ru')
  await expect(page.getByText('Активная группа').first()).toBeVisible()
})
