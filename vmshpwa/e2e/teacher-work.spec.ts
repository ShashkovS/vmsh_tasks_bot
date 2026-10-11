import { AUTH_PERSONAS, loginThroughUi } from './auth-personas'
import { expect, test } from './fixtures'

// docs/teacher-work.md: real admin route/API, no response mocks or production credentials.
test.use({ contextOptions: { reducedMotion: 'reduce' } })

test('Admin accounting tabs, calculation, export and protected teacher view', async ({
  page,
}, info) => {
  await loginThroughUi(page, AUTH_PERSONAS.admin, '/staff/users?tab=work&course=c-1')
  await expect(page.getByRole('tab', { name: 'Учёт работы', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Пересчитать учёт', exact: true }).click()
  await expect(page.getByText(/^Обновлено:/)).toBeVisible({ timeout: 30000 })
  await expect(page.getByRole('button', { name: 'Копировать TSV' })).toBeEnabled()
  for (const theme of ['light', 'dark']) {
    if (theme === 'dark')
      await page.getByRole('button', { name: 'Переключить на тёмную тему' }).click()
    for (const width of [1280, 390]) {
      await page.setViewportSize({ width, height: 900 })
      await page.screenshot({
        path: info.outputPath(`teacher-work-report-${theme}-${width}.png`),
        animations: 'disabled',
      })
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1),
      ).toBe(true)
    }
  }
  await page.getByRole('button', { name: 'Переключить на светлую тему' }).click()
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.getByRole('tab', { name: 'Настройки', exact: true }).click()
  await expect(page.getByLabel('Стандартное время очной смены, ч')).toHaveValue('2.3')
  await page.getByRole('tab', { name: 'Zoom', exact: true }).click()
  await expect(page.getByRole('checkbox', { name: 'Все подписи' })).toBeVisible()
  await page.getByRole('tab', { name: 'Очные смены', exact: true }).click()
  const text = '14 сентября\n201: Принимающий Тестовый (с 18:00)\n308 -- резерв.'
  await page.getByLabel('Распределение из оргчата').fill(text)
  await page.getByRole('button', { name: 'Предварительный просмотр' }).click()
  await expect(page.getByRole('table', { name: 'Предварительный просмотр смен' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Подтвердить фактические смены' })).toBeDisabled()
  await page.reload()
  await expect(page.getByLabel('Распределение из оргчата')).toHaveValue(text)
  for (const theme of ['light', 'dark']) {
    if (theme === 'dark')
      await page.getByRole('button', { name: 'Переключить на тёмную тему' }).click()
    for (const width of [1280, 390]) {
      await page.setViewportSize({ width, height: 900 })
      await page.screenshot({
        path: info.outputPath(`teacher-work-${theme}-${width}.png`),
        animations: 'disabled',
      })
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1),
      ).toBe(true)
    }
  }
  await page.evaluate(() => {
    document.documentElement.style.zoom = '2'
  })
  await expect(page.getByRole('button', { name: 'Предварительный просмотр' })).toBeVisible()
})

test('Teacher cannot read work accounting', async ({ page }) => {
  await loginThroughUi(page, AUTH_PERSONAS.teacher, '/staff/users?tab=work&course=c-1')
  await expect(page.getByText('Учёт работы доступен только администратору.')).toBeVisible()
  await expect(page.getByRole('tab', { name: 'Учёт работы', exact: true })).toHaveCount(0)
  const response = await page.request.get('/staff/api/v1/teacher-work/report?courseId=c-1')
  expect(response.status()).toBe(403)
})

test('Admin confirms school work and a written override survives recalculation', async ({
  page,
}, info) => {
  const fixtures: Record<string, [number, number]> = {
    chromium: [19931, 9901],
    webkit: [19932, 9902],
    firefox: [19933, 9903],
  }
  const fixture = fixtures[info.project.name]
  if (!fixture) throw new Error('Unknown browser fixture')
  const [fixtureId, writtenLesson] = fixture
  await loginThroughUi(
    page,
    AUTH_PERSONAS.admin,
    '/staff/users?tab=work&workSection=school&course=c-1',
  )
  await page.getByRole('tab', { name: 'Очные смены', exact: true }).click()
  await page.getByLabel('Распределение из оргчата').fill('9 сентября\n201: Учитель (с 13:00)')
  await page.getByRole('button', { name: 'Предварительный просмотр' }).click()
  await page.getByLabel('Очное событие').selectOption(`ipe-${fixtureId}`)
  await page.getByLabel('Преподаватель для Учитель').selectOption(`u-${fixtureId}`)
  const command = () =>
    page.waitForResponse(
      (r) => r.request().method() === 'POST' && r.url().endsWith('/teacher-work/command'),
    )
  const confirmed = command()
  await page.getByRole('button', { name: 'Подтвердить фактические смены' }).click()
  expect((await confirmed).status()).toBe(200)
  await expect(page.getByText('Сохранённое распределение: версия 1.')).toBeVisible()
  await page.reload()
  await expect(page.getByLabel('Преподаватель для Учитель')).toHaveValue(`u-${fixtureId}`)
  await page.getByRole('tab', { name: 'Отчёт', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Пересчитать учёт', exact: true })).toBeEnabled()
  const writtenCell = page.getByRole('button', {
    name: new RegExp(`Преподаватель Тестовый, занятие ${writtenLesson}, ✏,`),
  })
  await writtenCell.click()
  await page.getByLabel('Итоговые часы вручную').fill('1.25')
  await page.getByLabel('Причина поправки').fill('Уточнение времени после сверки')
  const saved = command()
  await page.getByRole('button', { name: 'Сохранить поправку', exact: true }).click()
  expect((await saved).status()).toBe(200)
  await expect(page.getByRole('button', { name: 'Вернуть расчётное время' })).toBeVisible()
  await page.keyboard.press('Escape')
  await page.getByRole('button', { name: 'Пересчитать учёт', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Пересчитать учёт', exact: true })).toBeEnabled()
  await writtenCell.click()
  await expect(page.getByLabel('Итоговые часы вручную')).toHaveValue('1.25')
  const reset = command()
  await page.getByRole('button', { name: 'Вернуть расчётное время' }).click()
  expect((await reset).status()).toBe(200)
  await expect(page.getByRole('button', { name: 'Вернуть расчётное время' })).toHaveCount(0)
})
