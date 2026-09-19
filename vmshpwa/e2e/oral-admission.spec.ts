import contentFixture from '../../pwa_tests/fixtures/content/e2e-content-v1.json' with { type: 'json' }

import { AUTH_PERSONAS, loginThroughUi } from './auth-personas'
import { expect, test } from './fixtures'

test.setTimeout(90_000)

const targetByProject: Record<string, { lessonNumber: number; ordinal: number }> = {
  chromium: { lessonNumber: 921, ordinal: 1 },
  webkit: { lessonNumber: 922, ordinal: 2 },
  firefox: { lessonNumber: 923, ordinal: 3 },
}

test('Phase 7: Student joins an oral window and Teacher records the legacy result', async ({
  page,
}, testInfo) => {
  const project = testInfo.project.name
  const target = targetByProject[project]
  if (target === undefined) throw new Error(`No oral E2E lesson for ${project}`)
  const groupLessonId = `gl-${target.lessonNumber}`
  const title = `Устная E2E ${project}`

  await loginThroughUi(page, AUTH_PERSONAS.student, '/student/tasks')
  await page.goto(
    `/student/tasks?course=${contentFixture.coursePublicId}` +
      `&group=${contentFixture.groupPublicId}&lesson=${target.lessonNumber}`,
  )
  const task = page.getByRole('heading', { name: `1 ${title}`, exact: true })
  const earlier = page.getByRole('button', { name: 'Показать более ранние занятия' })
  await expect(task.or(earlier).first()).toBeVisible()
  if (!(await task.isVisible())) await earlier.click()
  await expect(task).toBeVisible()
  await task
    .locator('xpath=ancestor::article')
    .getByRole('button', { name: 'Открыть задачу 1' })
    .click()
  await expect(page.getByRole('heading', { name: `1 ${title}`, exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Устный приём' })).toBeVisible()
  await expect(page.getByText('Задачу также можно отправить письменно ниже.')).toBeVisible()

  const joinResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'GET' &&
      new URL(response.url()).pathname.endsWith(`/oral-windows/ow-${target.lessonNumber}/join`),
  )
  await page.getByRole('button', { name: 'Подключиться к Zoom' }).click()
  expect((await joinResponse).status()).toBe(200)
  await expect(page.getByText(`17990${target.ordinal}`)).toBeVisible()
  await expect(page.getByRole('link', { name: 'Подключиться к Zoom' })).toHaveAttribute(
    'href',
    `https://zoom.example.test/j/${target.ordinal}`,
  )

  await loginThroughUi(
    page,
    AUTH_PERSONAS.teacher,
    `/staff/oral?groupLesson=${groupLessonId}&tab=results`,
  )
  await expect(page.getByRole('heading', { name: 'Результаты устного приёма' })).toBeVisible()
  await page.getByRole('combobox', { name: 'Школьник' }).click()
  await page.getByRole('option', { name: 'Тестовый-Онлайн Алексей' }).click()
  await page.getByRole('button', { name: '1: Зачтено' }).click()
  await page.getByRole('button', { name: /Внятно, уверенно/ }).click()

  const resultResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname ===
        `/staff/api/v1/group-lessons/${groupLessonId}/oral-results`,
  )
  await page.getByRole('button', { name: 'Сохранить результаты' }).click()
  expect((await resultResponse).status()).toBe(201)
  await expect(page.getByRole('status')).toContainText('Результаты сохранены')

  await page.goto(
    `/student/tasks?course=${contentFixture.coursePublicId}` +
      `&group=${contentFixture.groupPublicId}&lesson=${target.lessonNumber}`,
  )
  await expect(task.or(earlier).first()).toBeVisible()
  if (!(await task.isVisible())) await earlier.click()
  await expect(
    page
      .getByRole('heading', { name: `1 ${title}`, exact: true })
      .locator('xpath=ancestor::article'),
  ).toContainText('Зачтено')

  await page.goto(`/student/progress?course=${contentFixture.coursePublicId}`)
  await expect(page.getByRole('heading', { name: 'Прогресс' })).toBeVisible()
  const lessonProgress = page
    .getByText(`Занятие ${target.lessonNumber}`, { exact: true })
    .locator('xpath=..')
  await expect(lessonProgress).toContainText('1 зачтено из 1')

  // A later teacher round is a real correction: the legacy positive result is
  // superseded, while the Student progress read is recalculated from SQLite.
  await page.goto(`/staff/oral?groupLesson=${groupLessonId}&tab=results`)
  await page.getByRole('combobox', { name: 'Школьник' }).click()
  await page.getByRole('option', { name: 'Тестовый-Онлайн Алексей' }).click()
  await page.getByRole('button', { name: '1: Не зачтено' }).click()
  const correctionResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname ===
        `/staff/api/v1/group-lessons/${groupLessonId}/oral-results`,
  )
  await page.getByRole('button', { name: 'Сохранить результаты' }).click()
  expect((await correctionResponse).status()).toBe(201)

  await page.goto(`/student/progress?course=${contentFixture.coursePublicId}`)
  const correctedLesson = page
    .getByText(`Занятие ${target.lessonNumber}`, { exact: true })
    .locator('xpath=..')
  await expect(correctedLesson).toContainText('0 зачтено из 1')
  await expect(
    page.getByRole('figure', { name: /С другими школьниками здесь не сравниваем/ }),
  ).toBeVisible()

  const progressPayload = await page.evaluate(async (courseId) => {
    const response = await fetch(`/student/api/v1/courses/${courseId}/progress`)
    const payload: unknown = await response.json()
    return payload
  }, contentFixture.coursePublicId)
  expect(JSON.stringify(progressPayload)).not.toMatch(
    /"(?:cohort|distribution|percentile|rank|studentMarker)"/,
  )
})
