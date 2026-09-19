import { mkdir } from 'node:fs/promises'
import { AUTH_PERSONAS, loginThroughUi } from './auth-personas'
import { expect, test } from './fixtures'

// Real queue, leases and URL return paths; docs/serial-review.md.
test('Review queue: filters, summary, colleague lease and return navigation', async ({
  page,
  secondaryContext,
}, testInfo) => {
  test.setTimeout(120_000)
  const browser = testInfo.project.name
  const title = `E2E проверка ${browser}`
  await page.clock.install({ time: new Date('2026-07-28T12:10:00Z') })
  await loginThroughUi(page, AUTH_PERSONAS.teacher, '/staff/review')
  let mutations = 0
  page.on('request', (request) => {
    if (request.method() === 'POST' && request.url().includes('/review/items/')) mutations++
  })
  const summary = page.getByRole('definition')
  await expect(summary).toHaveCount(3)
  await expect(page.getByText(/свободно из/)).toHaveCount(0)
  const card = page.getByRole('article').filter({ hasText: title })
  await expect(card).toContainText('Ждут проверки: 1 работа')
  const waiting = card.getByText(/Самая давняя работа ждёт/)
  const before = await waiting.textContent()
  await page.clock.fastForward(60_000)
  // Fixtures are recent; minute updates must not depend on a queue response.
  await expect(waiting).not.toHaveText(before!)
  await page.getByLabel('Порядок задач').selectOption('count')
  const courseSelect = page.getByRole('combobox', { name: 'Курс', exact: true })
  const course = await courseSelect.locator('option').nth(1).getAttribute('value')
  await courseSelect.selectOption(course)
  const groupSelect = page.getByRole('combobox', { name: 'Группа', exact: true })
  const group = await groupSelect.locator('option').nth(1).getAttribute('value')
  await groupSelect.selectOption(group)
  await page.reload()
  await expect(courseSelect).toHaveValue(course!)
  await expect(groupSelect).toHaveValue(group!)
  await expect(page.getByLabel('Порядок задач')).toHaveValue('count')

  expect(mutations).toBe(0)
  const busyBefore = parseInt((await summary.nth(2).textContent())!)
  const admin = await secondaryContext.newPage()
  await loginThroughUi(admin, AUTH_PERSONAS.admin, '/staff/review')
  await admin.getByRole('button', { name: 'Все работы', exact: true }).click()
  await admin
    .getByRole('row')
    .filter({ hasText: title })
    .getByRole('button', { name: 'Открыть', exact: true })
    .click()
  await expect(admin.getByRole('heading', { name: 'Проверка работы', exact: true })).toBeVisible()
  await expect(card).toContainText('У других преподавателей: 1')
  await expect
    .poll(async () => parseInt((await summary.nth(2).textContent())!))
    .toBe(busyBefore + 1)
  await expect(card.getByRole('link', { name: 'Проверять подряд' })).toBeDisabled()
  await expect(card).toContainText('Все работы уже взяты другими преподавателями')

  const folder = 'docs/assets/review-queue'
  await mkdir(folder, { recursive: true })
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.screenshot({ path: `${folder}/${browser}-desktop.png`, fullPage: true })
  await page.evaluate(() => {
    document.documentElement.style.zoom = '2'
  })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  )
  await expect(courseSelect).toBeVisible()
  await page.screenshot({ path: `${folder}/${browser}-zoom.png`, fullPage: true })
  await page.evaluate(() => {
    document.documentElement.style.zoom = ''
  })
  for (const width of [320, 390]) {
    await page.setViewportSize({ width, height: 844 })
    await page
      .getByRole('button', {
        name: width === 320 ? 'Переключить на тёмную тему' : 'Переключить на светлую тему',
      })
      .click()
    if (width === 320) await expect(page.locator('html')).toHaveClass(/dark/)
    else await expect(page.locator('html')).not.toHaveClass(/dark/)
    await expect(card).toBeVisible()
    expect((await courseSelect.boundingBox())!.height).toBeGreaterThanOrEqual(32)
    expect((await groupSelect.boundingBox())!.height).toBeGreaterThanOrEqual(32)
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBe(true)
    await courseSelect.focus()
    await expect(courseSelect).toBeFocused()
    await page.keyboard.press('Tab')
    await expect(groupSelect).toBeFocused()
    await page.screenshot({ path: `${folder}/${browser}-${width}.png`, fullPage: true })
  }
  await admin.getByRole('button', { name: 'Отказаться от проверки', exact: true }).click()
  await expect(card.getByRole('link', { name: 'Проверять подряд' })).toBeEnabled()
  await expect.poll(async () => parseInt((await summary.nth(2).textContent())!)).toBe(busyBefore)
  await page.setViewportSize({ width: 1280, height: 900 })
  await card.getByRole('link', { name: 'Проверять подряд' }).click()
  await expect(page).toHaveURL(/\/review\/series\//)
  await page.getByRole('link', { name: 'К списку задач' }).click()
  await expect(courseSelect).toHaveValue(course!)
  await expect(groupSelect).toHaveValue(group!)
  await expect(page.getByLabel('Порядок задач')).toHaveValue('count')
  await page.getByRole('button', { name: 'Все работы', exact: true }).click()
  await expect(page.getByText(/В очереди:/)).toHaveCount(0)
  await page.getByRole('button', { name: 'Ученик', exact: true }).click()
  await page.reload()
  await expect(page).toHaveURL(/queueTableSort=student/)
  await expect(page.getByRole('button', { name: 'Все работы', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await page
    .getByRole('row')
    .filter({ hasText: title })
    .getByRole('button', { name: 'Открыть', exact: true })
    .click()
  await page.getByRole('button', { name: 'Отказаться от проверки', exact: true }).click()
  await expect(courseSelect).toHaveValue(course!)
  await expect(page).toHaveURL(/queueTableSort=student/)
  const emptyUrl = new URL(page.url())
  emptyUrl.searchParams.set('queueGroup', 'g-999999')
  await page.goto(emptyUrl.href)
  await expect(page.getByText('По выбранным фильтрам работ нет')).toBeVisible()
  await expect(page.getByText('Все работы проверены')).toHaveCount(0)
  await page.getByRole('button', { name: 'Сбросить фильтры', exact: true }).click()
  await expect(courseSelect).toHaveValue('')
  await expect(groupSelect).toHaveValue('')
})
