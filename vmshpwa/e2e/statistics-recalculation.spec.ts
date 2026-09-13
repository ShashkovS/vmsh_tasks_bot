import { execFileSync } from 'node:child_process'
import { AUTH_PERSONAS, loginThroughUi } from './auth-personas'
import { expect, test } from './fixtures'

// docs/lesson-statistics.md: admin operation, reload, themes and scoped density.
test('Admin recalculates whole course and retains statistics filters', async ({ page }, info) => {
  execFileSync('.venv/bin/python', ['-m', 'vmshpwa.scripts.seed_e2e_statistics_recalculation'], {
    cwd: '..',
    env: {
      ...process.env,
      VMSH_RUNTIME_PROFILE: 'pwa-e2e',
      VMSH_INSTANCE: 'e2e',
      VMSH_DB_FILENAME: 'db/vmshpwa_e2e.sqlite3',
      VMSH_ANALYTICS_DB_FILENAME: '.runtime/vmshpwa/e2e/analytics.sqlite3',
      VMSH_MEDIA_ROOT: '.runtime/vmshpwa/e2e',
      VMSH_NATS_SERVER: '',
      VMSH_NATS_TOPIC_PREFIX: 'vmshpwa_e2e',
      VMSH_PWA_PROTOTYPE: 'true',
    },
  })
  await loginThroughUi(page, AUTH_PERSONAS.admin, '/staff/statistics?course=c-1&lesson=931')
  const recalculate = page.getByRole('button', { name: 'Пересчитать сложность', exact: true })
  await expect(recalculate).toBeEnabled()
  await expect(page.getByText('Зачёт — 1 балл', { exact: false })).toHaveCount(0)
  let starts = 0
  page.on('request', (request) => {
    if (request.method() === 'POST' && request.url().includes('/statistics/recalculate')) starts++
  })
  await page.getByRole('button', { name: 'Обновить статистику' }).click()
  await expect(recalculate).toBeEnabled()
  expect(starts).toBe(0)
  await recalculate.click()
  await expect(page.getByText(/Пересчитано:/)).toBeVisible({ timeout: 30000 })
  expect(starts).toBe(1)
  await page.reload()
  await expect(page.getByText(/Пересчитано:/)).toBeVisible()
  await expect(page).toHaveURL((url) => url.searchParams.get('lesson') === '931')
  const violin = page.getByRole('img', { name: /Число решённых задач.*Распределение/ }).first()
  await expect(violin).toBeVisible()
  expect((await violin.boundingBox())!.height).toBeCloseTo(260, 0)
  for (const theme of ['light', 'dark']) {
    if (theme === 'dark')
      await page.getByRole('button', { name: 'Переключить на тёмную тему' }).click()
    for (const width of [1280, 390, 320]) {
      await page.setViewportSize({ width, height: 900 })
      await expect(recalculate).toBeVisible()
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
        true,
      )
      await page.screenshot({
        path: info.outputPath(`statistics-${theme}-${width}.png`),
        fullPage: true,
      })
    }
  }
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.evaluate(() => {
    document.documentElement.style.zoom = '2'
  })
  await expect(recalculate).toBeVisible()
  await recalculate.focus()
  await expect(recalculate).toBeFocused()
  await page.screenshot({ path: info.outputPath('statistics-200-percent.png'), fullPage: true })
})

test('Teacher sees dense statistics without administrative action', async ({ page }) => {
  await loginThroughUi(page, AUTH_PERSONAS.teacher, '/staff/statistics?course=c-1&lesson=41')
  await expect(page.getByRole('button', { name: 'Обновить статистику' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Пересчитать сложность' })).toHaveCount(0)
})
