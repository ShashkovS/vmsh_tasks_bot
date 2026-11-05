import { AUTH_PERSONAS, loginThroughUi } from './auth-personas'
import { expect, test } from './fixtures'

// docs/lesson-statistics.md: real 700 × 20 matrix, no pagination or nested vertical scroll.
test('Statistics tabs, channels and complete large matrix', async ({ page }, info) => {
  const lesson = { chromium: 35101, webkit: 35102, firefox: 35103 }[info.project.name]!
  const calls: string[] = []
  page.on('request', (r) => {
    if (r.url().includes('/statistics')) calls.push(r.url())
  })
  await loginThroughUi(page, AUTH_PERSONAS.admin, `/staff/statistics?course=c-1&lesson=${lesson}`)
  await expect(page.getByRole('table', { name: 'Сводка курса', exact: true })).toBeVisible()
  expect(calls.some((url) => url.includes('/api/v1/statistics?'))).toBe(false)
  await page.getByRole('button', { name: 'Таблица плюсов', exact: true }).click()
  const table = page.getByRole('table', { name: 'Таблица плюсов', exact: true })
  await expect(table.locator('tbody tr')).toHaveCount(700)
  await expect(table.getByRole('columnheader')).toHaveCount(22)
  await expect(page).toHaveURL(/view=plus-table/)
  await page.reload()
  await expect(table.locator('tbody tr')).toHaveCount(700)
  await page.getByRole('button', { name: 'Продолжающие', exact: true }).click()
  await expect(page.getByRole('combobox', { name: 'Занятие', exact: true })).toHaveValue(
    String(lesson),
  )
  await expect(table.locator('tbody tr')).toHaveCount(0)
  await page.getByRole('button', { name: 'Начинающие', exact: true }).click()
  await expect(table.locator('tbody tr')).toHaveCount(700)
  for (const theme of ['light', 'dark']) {
    if (theme === 'dark')
      await page.getByRole('button', { name: 'Переключить на тёмную тему' }).click()
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: 900 })
      const header = await table.locator('thead').boundingBox()
      const firstRow = await table.locator('tbody tr').first().boundingBox()
      expect(header!.y + header!.height).toBeLessThanOrEqual(firstRow!.y + 1)
      const dimensions = await table.evaluate((element) => {
        const parent = element.parentElement!
        return {
          height: parent.clientHeight,
          content: parent.scrollHeight,
          width: parent.clientWidth,
          full: parent.scrollWidth,
        }
      })
      expect(dimensions.content).toBeLessThanOrEqual(dimensions.height + 1)
      if (width === 1440) expect(dimensions.full).toBeLessThanOrEqual(dimensions.width + 1)
      await page.screenshot({ path: info.outputPath(`plus-${theme}-${width}.png`) })
    }
  }
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.evaluate(() => {
    document.documentElement.style.zoom = '2'
  })
  await table.locator('tbody tr').last().scrollIntoViewIfNeeded()
  await expect(table.locator('tbody tr').last()).toBeVisible()
  await page.getByRole('button', { name: 'Сводка курса', exact: true }).focus()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('table', { name: 'Сводка курса', exact: true })).toBeVisible()
})
