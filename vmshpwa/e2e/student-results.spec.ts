import { AUTH_PERSONAS, loginThroughUi } from './auth-personas'
import { expect, test } from './fixtures'
import {
  reviewHistoryDetailResponseSchema,
  studentResultHistorySchema,
} from '../packages/contracts/src'

// docs/student-results.md: real admin archive, production bundles, all three engines.
test('Student archive: fuzzy search, multiple levels, complete history, URL and responsive layout', async ({
  page,
  context,
}, info) => {
  test.setTimeout(120_000)
  // The archive fixture attaches to review fixture 9701, seeded first for Chromium.
  const archivedProblemTitle = 'E2E проверка chromium'
  await page.setViewportSize({ width: 1440, height: 1000 })
  await loginThroughUi(page, AUTH_PERSONAS.admin, '/staff/student-results')
  await page.getByLabel('Фамилия и имя').fill('Архивво Александр')
  const student = page.getByRole('button', { name: /Архивов Александр/ })
  await expect(student).toContainText('Михайлович')
  await student.click()
  await expect(page).toHaveURL(/student=u-31301/)
  await expect(page).toHaveURL(/lesson=9701/)
  const detail = page.getByRole('region', { name: 'История занятия', exact: true })
  await expect(detail.getByText('Решение продвинутого уровня из Telegram.')).toBeVisible()
  await expect(detail.getByRole('heading', { name: 'Задача 3', exact: true })).toHaveCount(0)
  await expect(page.getByText('НЕОТПРАВЛЕННЫЙ ЧЕРНОВИК')).toHaveCount(0)
  await expect(
    detail.getByText('Досылка из Telegram: добавил рисунок.', { exact: true }),
  ).toHaveCount(1)
  await expect(detail.getByText('Исправление проверки: обоснование полное.')).toBeVisible()
  await expect(detail.getByText('Ответ на тест · Приложение')).toBeVisible()
  await expect(detail.getByText('Файл не сохранился или недоступен.')).toBeVisible()
  await expect(detail.getByRole('button', { name: /Ещё 50 событий/ })).toBeVisible()
  await expect(
    // The asynchronously loaded statement also has an h2 with this title.
    detail.getByRole('heading', { name: new RegExp(archivedProblemTitle), level: 4 }),
  ).toBeVisible()
  await page.screenshot({ path: info.outputPath('results-desktop.png'), animations: 'disabled' })
  await detail.getByRole('button', { name: /Ещё 50 событий/ }).click()
  await expect(detail.getByText('Архивная досылка 55: уточнение решения.')).toBeVisible()
  await expect(detail.getByRole('button', { name: /Ещё 50 событий/ })).toHaveCount(0)
  const photo = detail.getByAltText('Вложение к посылке').first()
  await photo.scrollIntoViewIfNeeded()
  await expect
    .poll(() => photo.evaluate((image) => (image as HTMLImageElement).naturalWidth))
    .toBe(640)
  const annotated = detail.getByAltText('Решение с отметками преподавателя').first()
  await annotated.scrollIntoViewIfNeeded()
  await expect
    .poll(() => annotated.evaluate((image) => (image as HTMLImageElement).naturalWidth))
    .toBe(640)
  await page.screenshot({
    path: info.outputPath('results-photo-annotations.png'),
    animations: 'disabled',
  })
  const condition = detail.getByRole('button', { name: 'Условие на момент отправки' }).first()
  await condition.click()
  await expect(page.getByRole('dialog')).toContainText(archivedProblemTitle)
  await page.keyboard.press('Escape')
  await expect(condition).toBeFocused()
  const grade = page.getByRole('button', { name: /История оценки · задача 9701н\.3/ }).first()
  await grade.click()
  await expect(page.getByRole('dialog')).toContainText('Очное занятие')
  await page.keyboard.press('Escape')
  await expect(grade).toBeFocused()
  await page.getByRole('combobox', { name: 'Курс', exact: true }).selectOption('c-31301')
  await expect(detail).toContainText('Решение из другого курса.')
  await expect(page).toHaveURL(/course=c-31301/)
  await expect(page).toHaveURL(/lesson=7/)
  await page.getByRole('combobox', { name: 'Курс', exact: true }).selectOption('c-1')
  await expect(detail).toContainText('Исправление проверки: обоснование полное.')
  const url = page.url()
  await detail.getByRole('link', { name: 'Открыть проверку' }).first().click()
  await expect(page).toHaveURL(/\/staff\/review\/history\?review=/)
  await expect(
    page.getByText('Исправление проверки: обоснование полное.', { exact: true }).first(),
  ).toBeVisible()
  await page.goBack()
  await expect(page).toHaveURL(url)
  await expect(page.getByRole('heading', { name: 'Архивов Александр' })).toBeVisible()
  await page.getByRole('combobox', { name: 'Занятие', exact: true }).selectOption('9702')
  await expect(detail).toContainText('Отправленных решений и тестовых попыток в этом занятии нет.')
  await page.getByRole('button', { name: 'Занятие 9701', exact: true }).click()
  await expect(detail).toBeFocused()
  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 844 })
    await page.evaluate(() => window.scrollTo(0, 0))
    await expect(
      page.getByRole('heading', { name: 'Результаты школьника', exact: true }),
    ).toBeVisible()
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBeTruthy()
    await page.screenshot({
      path: info.outputPath(`results-mobile-${width}.png`),
      animations: 'disabled',
    })
  }
  await page.getByRole('button', { name: 'Переключить на тёмную тему' }).click()
  await page.screenshot({ path: info.outputPath('results-dark.png'), animations: 'disabled' })
  await page.setViewportSize({ width: 1280, height: 1000 })
  await page.evaluate(() => {
    document.documentElement.style.zoom = '2'
  })
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBeTruthy()
  await page.getByRole('button', { name: 'Обновить', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Архивов Александр' })).toBeVisible()
  await page.screenshot({ path: info.outputPath('results-zoom-200.png'), animations: 'disabled' })
  await context.setOffline(true)
  await expect(page.getByText(/Нет соединения. Доступны загруженные результаты/)).toBeVisible()
  await page.getByRole('button', { name: 'Обновить', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Архивов Александр' })).toBeVisible()
  await context.setOffline(false)
  await expect(page.getByText(/Нет соединения. Доступны загруженные результаты/)).toHaveCount(0)
})

// docs/review-history.md: old Teacher/Admin review contains the same saved replies
// as the admin archive, while correction retains only its immutable evidence.
test('Old review: Teacher and Admin read full mixed dialogue and correct original evidence', async ({
  page,
  secondaryContext,
}, info) => {
  test.setTimeout(120_000)
  await loginThroughUi(page, AUTH_PERSONAS.admin, '/staff/student-results')
  const archive = studentResultHistorySchema.parse(
    await page.evaluate(async (): Promise<unknown> =>
      (await fetch('/staff/api/v1/student-results/u-31301/problems/p-9701/history')).json(),
    ),
  )
  const reviewId = archive.events.find((event) => event.kind === 'review')?.reviewId
  if (!reviewId) throw new Error('Archive fixture has no old review')
  const teacher = await secondaryContext.newPage()
  await loginThroughUi(teacher, AUTH_PERSONAS.teacher, `/staff/review/history?review=${reviewId}`)
  const dialogue = teacher.getByRole('region', { name: 'История переписки и проверок' })
  await expect(dialogue.getByText('Идея верная, обоснуйте равенство углов.')).toBeVisible()
  await expect(
    dialogue.getByText('Рассмотрим треугольники ABC и ADC. У них общая сторона AC.'),
  ).toBeVisible()
  await expect(
    dialogue.getByText('Досылка из Telegram: добавил рисунок.', { exact: true }),
  ).toHaveCount(1)
  await dialogue.getByRole('button', { name: /Ещё 50 событий/ }).click()
  await expect(dialogue.getByText('Архивная досылка 55: уточнение решения.')).toBeVisible()
  await expect(dialogue.getByText('НЕОТПРАВЛЕННЫЙ ЧЕРНОВИК')).toHaveCount(0)
  await teacher.getByLabel('Комментарий').fill('Черновик исправления старой проверки')
  await teacher.reload()
  await expect(teacher.getByLabel('Комментарий')).toHaveValue(
    'Черновик исправления старой проверки',
  )
  await expect(
    dialogue.getByText('Досылка из Telegram: добавил рисунок.', { exact: true }),
  ).toHaveCount(1)
  await teacher.close()

  await page.goto(`/staff/review/history?review=${reviewId}`)
  const adminDialogue = page.getByRole('region', { name: 'История переписки и проверок' })
  await expect(
    adminDialogue.getByText('Рассмотрим треугольники ABC и ADC. У них общая сторона AC.'),
  ).toBeVisible()
  await adminDialogue.getByRole('button', { name: /Ещё 50 событий/ }).click()
  await expect(adminDialogue.getByText('Архивная досылка 55: уточнение решения.')).toBeVisible()
  const original = reviewHistoryDetailResponseSchema.parse(
    await page.evaluate(
      async (id): Promise<unknown> =>
        (await fetch(`/staff/api/v1/review/history?review=${id}`)).json(),
      reviewId,
    ),
  )
  await page.setViewportSize({ width: 1280, height: 900 })
  for (const theme of ['light', 'dark']) {
    await page.evaluate((value) => {
      document.documentElement.dataset.theme = value
      document.documentElement.classList.toggle('dark', value === 'dark')
    }, theme)
    await adminDialogue.scrollIntoViewIfNeeded()
    await page.screenshot({
      path: info.outputPath(`old-review-${theme}.png`),
      animations: 'disabled',
    })
  }
  await page.getByLabel('Комментарий').fill('Старая проверка: исходные материалы сохранены.')
  await page.getByRole('button', { name: /Половина/ }).click()
  page.once('dialog', (dialog) => dialog.accept())
  const receipt = page.waitForResponse(
    (response) => response.request().method() === 'POST' && response.url().endsWith('/correction'),
  )
  await page.getByRole('button', { name: 'Отправить вердикт' }).click()
  const response = await receipt
  expect(response.status()).toBe(200)
  const correction = (await response.json()) as { correction: { reviewId: string } }
  await page.goto(`/staff/review/history?review=${correction.correction.reviewId}`)
  await expect(
    page
      .getByRole('region', { name: 'История переписки и проверок' })
      .getByText('Досылка из Telegram: добавил рисунок.', { exact: true }),
  ).toHaveCount(1)
  const corrected = reviewHistoryDetailResponseSchema.parse(
    await page.evaluate(
      async (id): Promise<unknown> =>
        (await fetch(`/staff/api/v1/review/history?review=${id}`)).json(),
      correction.correction.reviewId,
    ),
  )
  expect(corrected.detail.entries).toEqual(original.detail.entries)
})

test('Student archive refuses teacher access', async ({ page }) => {
  await loginThroughUi(page, AUTH_PERSONAS.teacher, '/staff/')
  await page.goto('/staff/student-results')
  await expect(page.getByRole('heading', { name: 'Нет доступа', exact: true })).toBeVisible()
  await expect(page.getByLabel('Фамилия и имя')).toHaveCount(0)
  const response = await page.request.get('/staff/api/v1/student-results/directory')
  expect(response.status()).toBe(403)
})
