import { AUTH_PERSONAS, loginThroughUi } from './auth-personas'
import { expect, test } from './fixtures'

// English interface: dev/development-plan/24-i18n.md, docs/i18n.md.
// P0: the device cookie selects the English catalog before the first render;
// copy that is not translated yet stays Russian. P1 replaces the cookie setup
// with the profile language selector.

test('English device language reaches the Student profile catalog', async ({
  page,
  context,
  baseURL,
}) => {
  await context.addCookies([{ name: 'vmsh-locale', value: 'en', url: baseURL ?? '' }])
  await loginThroughUi(page, AUTH_PERSONAS.student, '/student/profile')

  await expect(page.locator('html')).toHaveAttribute('lang', 'en')
  await expect(page.getByText('Active group').first()).toBeVisible()
  await expect(page.getByText('Формат занятий').first()).toBeVisible()
})

test('Russian stays the default without a device choice', async ({ page }) => {
  await loginThroughUi(page, AUTH_PERSONAS.student, '/student/profile')

  await expect(page.locator('html')).toHaveAttribute('lang', 'ru')
  await expect(page.getByText('Активная группа').first()).toBeVisible()
})
