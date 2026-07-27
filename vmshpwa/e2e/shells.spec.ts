import { AUTH_PERSONAS, loginThroughUi, type AuthPersona } from './auth-personas'
import { expect, test } from './fixtures'

test.beforeEach(async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
})

const apps = [
  {
    audience: 'student',
    persona: AUTH_PERSONAS.student,
    title: 'ВМШ 179',
    detail: '/student/tasks/geometry-7',
  },
  {
    audience: 'family',
    persona: AUTH_PERSONAS.family,
    title: 'ВМШ 179',
    detail: '/family/children/masha',
  },
  {
    audience: 'staff',
    persona: AUTH_PERSONAS.teacher,
    title: 'ВМШ 179',
    detail: '/staff/review/submission-17',
  },
] satisfies Array<{
  audience: 'student' | 'family' | 'staff'
  persona: AuthPersona
  title: string
  detail: string
}>

for (const app of apps) {
  test(`${app.audience}: shell, base path and history fallback`, async ({ page }) => {
    await loginThroughUi(page, app.persona)
    await expect(page.getByRole('link', { name: app.title }).first()).toBeVisible()
    await expect(page.locator('[data-product]')).toHaveAttribute('data-product', app.audience)

    await page.goto(app.detail)
    await expect(page.locator('main')).toBeVisible()
    await expect(page.getByText('Страница не найдена')).toHaveCount(0)
  })
}

test('theme choice survives navigation within its application', async ({ page }) => {
  await loginThroughUi(page, AUTH_PERSONAS.student)
  await page.getByRole('button', { name: 'Переключить на тёмную тему' }).click()
  await expect(page.locator('html')).toHaveClass(/dark/)
  await page.reload()
  await expect(page.locator('html')).toHaveClass(/dark/)
})

test('@visual student current week', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await loginThroughUi(page, AUTH_PERSONAS.student)
  await expect(page.getByRole('link', { name: 'ВМШ 179' }).first()).toBeVisible()
  await page.evaluate(() => document.fonts.ready)
  const updateState = page.getByTestId('pwa-update-state')
  await updateState.waitFor({ state: 'visible', timeout: 2_000 }).catch(() => undefined)
  if (await updateState.isVisible())
    await updateState.getByRole('button', { name: 'Закрыть' }).click()
  await expect(page).toHaveScreenshot('student-current-week.png', { fullPage: true })
})

test('@visual staff weekly dashboard', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  await loginThroughUi(page, AUTH_PERSONAS.teacher)
  await expect(page.getByRole('link', { name: 'ВМШ 179' }).first()).toBeVisible()
  await page.evaluate(() => document.fonts.ready)
  await expect(page).toHaveScreenshot('staff-weekly-dashboard.png', { fullPage: true })
})
