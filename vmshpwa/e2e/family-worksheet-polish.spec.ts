import { AUTH_PERSONAS, loginThroughUi } from './auth-personas'
import { expect, test } from './fixtures'

// docs/family-worksheet-polish.md: real Family session and child-scoped API.
test('family reads earlier worksheets, switches viewing groups and has usable child/profile pages', async ({
  page,
}, testInfo) => {
  await loginThroughUi(page, AUTH_PERSONAS.family, '/family/children/u-101')
  await expect(page.getByRole('heading', { name: 'Алексей Тестовый-Онлайн' })).toBeVisible()
  const group = page.getByRole('combobox', { name: 'Группа', exact: true })
  await expect(group).toBeVisible()
  // The settings and the course now occupy the available desktop width.
  expect((await group.boundingBox())!.width).toBeGreaterThan(300)
  const history = page
    .locator('details')
    .filter({ has: page.getByText('История курса', { exact: true }) })
  await expect(history).toHaveAttribute('open', '')
  const numbers = await history
    .locator('li')
    .evaluateAll((items) =>
      items
        .map((item) => Number(item.textContent?.match(/Занятие (\d+)/)?.[1]))
        .filter(Number.isFinite),
    )
  expect(numbers).toEqual([...numbers].sort((a, b) => b - a))
  await page.screenshot({ path: testInfo.outputPath('child-desktop.png'), fullPage: true })
  await page.goto('/family/profile')
  await expect(
    page.getByRole('link', { name: 'Алексей Тестовый-Онлайн', exact: true }),
  ).toHaveAttribute('href', '/family/children/u-101')
  await expect(page.getByRole('link', { name: 'Мария Тестовая-Очно', exact: true })).toBeVisible()
  await expect(page.getByText('Отдельный семейный аккаунт без привязки к Telegram.')).toHaveCount(0)
  await page.screenshot({ path: testInfo.outputPath('profile.png'), fullPage: true })
  const lesson = { chromium: 32101, webkit: 32102, firefox: 32103 }[testInfo.project.name]!
  const path = `/family/tasks/math-5-7/${encodeURIComponent('н')}/${lesson}`
  await page.goto(path)
  await expect(
    page.getByRole('heading', { name: new RegExp(`Задача ${lesson}н\\.1\\.`) }),
  ).toBeVisible()
  await expect(page.getByText('Не начата', { exact: true }).first()).toBeVisible()
  await expect(page.getByRole('img', { name: 'Треугольник ABC' }).first()).toBeVisible()
  await expect(
    page.getByRole('button', { name: /Ответить|Открыть задачу|Задать вопрос/ }),
  ).toHaveCount(0)
  await expect(page.getByRole('textbox')).toHaveCount(0)
  const selector = page.getByRole('combobox', { name: 'Группа листка' })
  const options = await selector
    .locator('option')
    .evaluateAll((items) => items.map((item) => (item as HTMLOptionElement).value))
  expect(options.length).toBeGreaterThan(1)
  await selector.selectOption(options[1]!)
  await expect(
    page.getByText('Условие этого занятия для выбранной группы ещё не опубликовано.'),
  ).toBeVisible()
  await selector.selectOption(options[0]!)
  await expect(
    page.getByRole('heading', { name: new RegExp(`Задача ${lesson}н\\.1\\.`) }),
  ).toBeVisible()
  for (const width of [320, 390]) {
    await page.setViewportSize({ width, height: 800 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
      width,
    )
    await page.screenshot({ path: testInfo.outputPath(`worksheet-${width}.png`), fullPage: true })
  }
  await page.getByRole('button', { name: 'Переключить на тёмную тему' }).click()
  await page.screenshot({ path: testInfo.outputPath('worksheet-dark.png'), fullPage: true })
})
