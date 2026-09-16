import { test, expect, type Page } from './fixtures'
import { AUTH_PERSONAS, loginThroughUi } from './auth-personas'

async function mode(page: Page, value: string) {
  const response = await page.request.post('/__e2e__/service-mode', {
    headers: { 'X-VMSH-E2E-Control': process.env.VMSH_E2E_GATEWAY_CONTROL_TOKEN! },
    data: { mode: value },
  })
  expect(response.ok()).toBe(true)
}

// docs/smooth-redeploy.md: real HTTP gateway outage, no browser API mocks.
test('cold start waits through nginx HTML failure without a security warning', async ({ page }) => {
  await mode(page, 'bad-gateway')
  await page.goto('/student/')
  await expect(page.getByRole('heading', { name: 'Восстанавливаем соединение' })).toBeVisible()
  await expect(page.getByText('Не удалось безопасно открыть кабинет')).toHaveCount(0)
  await mode(page, 'updating')
  await expect(page.getByRole('heading', { name: 'Обновляем сервис' })).toBeVisible({
    timeout: 10000,
  })
  await mode(page, 'ready')
  await expect(page.getByRole('heading', { name: 'Обновляем сервис' })).toHaveCount(0, {
    timeout: 15000,
  })
  await expect(page.getByText('Не удалось безопасно открыть кабинет')).toHaveCount(0)
})

test('Family keeps connecting after a minute instead of turning waiting into an error', async ({
  page,
}) => {
  test.setTimeout(90000)
  await mode(page, 'updating')
  await page.goto('/family/')
  await expect(page.getByRole('heading', { name: 'Обновляем сервис' })).toBeVisible()
  await expect(
    page.getByText('Обновление занимает больше времени. Мы продолжаем подключаться.'),
  ).toBeVisible({ timeout: 65000 })
  await expect(page.getByRole('alert')).toHaveCount(0)
  await mode(page, 'ready')
  await expect(page.getByRole('heading', { name: 'Обновляем сервис' })).toHaveCount(0, {
    timeout: 15000,
  })
  await expect(page.getByText('Не удалось безопасно открыть кабинет')).toHaveCount(0)
})

test('a twenty-second deployment preserves an open form and saves exactly once', async ({
  page,
}, info) => {
  test.setTimeout(70000)
  const lesson = { chromium: 921, webkit: 922, firefox: 923 }[info.project.name]!
  await loginThroughUi(
    page,
    AUTH_PERSONAS.admin,
    `/staff/oral?groupLesson=gl-${lesson}&tab=windows`,
  )
  await page.getByLabel('Открывается', { exact: true }).fill('2030-10-07T18:00')
  await page.getByLabel('Закрывается', { exact: true }).fill('2030-10-07T20:00')
  await page.getByLabel('HTTPS-ссылка', { exact: true }).fill('https://zoom.example.test/redeploy')
  const scheduled = page.getByRole('region', { name: 'Настроенные окна' })
  const before = await scheduled.getByRole('button', { name: 'Клонировать', exact: true }).count()
  await mode(page, 'updating')
  await page.getByRole('button', { name: 'Создать выбранные окна', exact: true }).click()
  await expect(page.getByRole('status').filter({ hasText: 'Обновляем сервис' })).toBeVisible()
  await expect(page.getByLabel('HTTPS-ссылка', { exact: true })).toHaveValue(
    'https://zoom.example.test/redeploy',
  )
  // Deliberate real outage, longer than the previous bootstrap timeout.
  await page.waitForTimeout(20000)
  await expect(page.getByText('Не удалось безопасно открыть кабинет')).toHaveCount(0)
  await page.screenshot({ path: info.outputPath('service-updating.png'), fullPage: true })
  await mode(page, 'ready')
  await expect(page.getByRole('status').filter({ hasText: 'Окна созданы' })).toBeVisible({
    timeout: 15000,
  })
  await expect(scheduled.getByRole('button', { name: 'Клонировать', exact: true })).toHaveCount(
    before + 1,
  )
  await expect(page.getByRole('status').filter({ hasText: 'Обновляем сервис' })).toHaveCount(0)
})

test('a teacher mark survives a lost response with the same operation key', async ({
  page,
}, info) => {
  const lesson = { chromium: 931, webkit: 932, firefox: 933 }[info.project.name]!
  await loginThroughUi(
    page,
    {
      ...AUTH_PERSONAS.teacher,
      username: `live-${info.project.name}`,
      accountPublicId: `a-${19000 + lesson}`,
    },
    '/staff/oral?course=c-1',
  )
  await page.getByRole('searchbox', { name: 'Поиск школьника' }).fill('Тестовый-Онлайн Алексей')
  await page.getByRole('button', { name: /Тестовый-Онлайн Алексей/ }).click()
  await page.getByRole('combobox', { name: 'Занятие', exact: true }).selectOption(`gl-${lesson}`)
  const cell = page.getByRole('button', { name: new RegExp(`^Задача ${lesson}н\\.24:`) })
  await expect(cell).toBeVisible()
  const payloads: string[] = []
  page.on('request', (request) => {
    if (request.method() === 'POST' && request.url().endsWith('/live-marking/operations'))
      payloads.push(request.postData()!)
  })
  await mode(page, 'lose-receipt')
  await cell.click()
  await expect(cell).toHaveAccessibleName(/\+, моя оценка, Сохранено/, { timeout: 15000 })
  await expect.poll(() => payloads.length).toBe(2)
  expect(payloads[1]).toBe(payloads[0])
  await page.reload()
  await expect(cell).toHaveAccessibleName(/\+, моя оценка, Сохранено/)
})

test('a written answer keeps its photograph and resumes the existing outbox operation', async ({
  page,
}, info) => {
  test.setTimeout(70000)
  const lesson = { chromium: 32101, webkit: 32102, firefox: 32103 }[info.project.name]!
  await loginThroughUi(
    page,
    AUTH_PERSONAS.student,
    `/student/tasks/math-5-7/${encodeURIComponent('н')}/${lesson}`,
  )
  await page.getByRole('button', { name: 'Ответить', exact: true }).click()
  const submission = page.getByRole('region', { name: 'Сдать решение', exact: true })
  const text = `Решение во время обновления ${info.project.name}, прогон ${info.retry}`
  await page.getByRole('textbox', { name: 'Ваше решение', exact: true }).fill(text)
  await submission
    .locator('input[type="file"]')
    .first()
    .setInputFiles('../pwa_tests/fixtures/student-results-photo.webp')
  await expect(submission.getByText('готово', { exact: true })).toBeVisible()
  await mode(page, 'updating')
  const successfulSubmits: string[] = []
  page.on('response', (response) => {
    if (
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname.endsWith('/submit') &&
      response.ok()
    )
      successfulSubmits.push(response.url())
  })
  await submission.getByRole('button', { name: 'Отправить', exact: true }).click()
  await expect(
    page.getByRole('status').filter({ hasText: 'Обновляем сервис' }).first(),
  ).toBeVisible()
  await page.waitForTimeout(2000)
  expect(successfulSubmits).toHaveLength(0)
  await mode(page, 'ready')
  await expect.poll(() => successfulSubmits.length, { timeout: 15000 }).toBe(1)
  const message = submission
    .getByRole('list', { name: 'Переписка по задаче' })
    .locator(':scope > li')
    .filter({ hasText: text })
  await expect(message).toHaveCount(1)
  await expect(message.getByRole('img', { name: 'Страница 1' })).toBeVisible()
  await expect(page.getByText('Не удалось безопасно открыть кабинет')).toHaveCount(0)
  await expect(page.getByRole('status').filter({ hasText: 'Обновляем сервис' })).toHaveCount(0)
})
