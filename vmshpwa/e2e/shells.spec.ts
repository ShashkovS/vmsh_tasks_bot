import { expect, test } from './fixtures'

test.beforeEach(async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
})

const apps = [
  {
    audience: 'student',
    title: 'ВМШ 179',
    detail: '/student/tasks/geometry-7',
  },
  {
    audience: 'family',
    title: 'ВМШ 179',
    detail: '/family/children/masha',
  },
  {
    audience: 'staff',
    title: 'ВМШ 179',
    detail: '/staff/review/submission-17',
  },
] as const

for (const app of apps) {
  test(`${app.audience}: shell, base path and history fallback`, async ({ page }) => {
    await page.goto(`/${app.audience}/`)
    await expect(page.getByRole('link', { name: app.title }).first()).toBeVisible()
    await expect(page.locator('[data-product]')).toHaveAttribute('data-product', app.audience)

    await page.goto(app.detail)
    await expect(page.locator('main')).toBeVisible()
    await expect(page.getByText('Страница не найдена')).toHaveCount(0)
  })
}

test('theme choice survives navigation within its application', async ({ page }) => {
  await page.goto('/student/')
  await page.getByRole('button', { name: 'Переключить на тёмную тему' }).click()
  await expect(page.locator('html')).toHaveClass(/dark/)
  await page.reload()
  await expect(page.locator('html')).toHaveClass(/dark/)
})

test('@visual student current week', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/student/')
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
  await page.goto('/staff/')
  await expect(page.getByRole('link', { name: 'ВМШ 179' }).first()).toBeVisible()
  await page.evaluate(() => document.fonts.ready)
  await expect(page).toHaveScreenshot('staff-weekly-dashboard.png', { fullPage: true })
})
