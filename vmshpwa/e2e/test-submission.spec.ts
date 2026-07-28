import contentFixture from '../../pwa_tests/fixtures/content/e2e-content-v1.json' with { type: 'json' }

import { AUTH_PERSONAS, loginThroughUi } from './auth-personas'
import { expect, test, type Page } from './fixtures'

test.setTimeout(90_000)

type SubmissionTarget = (typeof contentFixture.submissionTargets)[number]

function targetForProject(projectName: string): SubmissionTarget {
  const target = contentFixture.submissionTargets.find(
    (candidate) => candidate.project === projectName,
  )
  if (!target) throw new Error(`No Phase-4 submission target for ${projectName}`)
  return target
}

function testProblemSource(
  projectName: string,
  retry: number,
  sourceTitle = 'Тестовая сдача',
  sourceItem = 'e2e',
): string {
  return String.raw`\documentclass{article}
\begin{document}
\problem[name=${sourceItem},title=${sourceTitle}]
Введите целое число 7. Этот текст не содержит правильного ответа в API поля ввода.
\eproblem
\end{document}
% ${projectName}, retry ${retry}
`
}

async function publishTestProblem(
  page: Page,
  target: SubmissionTarget,
  projectName: string,
  retry: number,
  options: {
    title?: string
    sourceTitle?: string
    sourceItem?: string
    correctAnswer?: string | null
  } = {},
): Promise<void> {
  const title = options.title ?? `Тестовая сдача ${projectName}`
  const workflow = page.getByTestId('content-workflow-condition')
  await expect(workflow).toBeVisible()
  await workflow.getByLabel('LaTeX-файл').setInputFiles({
    name: 'test-submission.tex',
    mimeType: 'application/x-tex',
    buffer: Buffer.from(
      testProblemSource(projectName, retry, options.sourceTitle, options.sourceItem),
      'utf-8',
    ),
  })

  const uploadResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname === '/staff/api/v1/content/uploads',
  )
  await workflow.getByRole('button', { name: 'Загрузить и проверить' }).click()
  expect((await uploadResponse).status()).toBe(201)

  // A Playwright retry reuses the same seeded server. Creating a new problem
  // branch keeps attempt counters independent from a failed prior run while
  // still exercising the production insert/publish workflow.
  const matching = workflow.getByLabel('Сопоставление задачи 1')
  await matching.selectOption('insert_new')
  await workflow.getByRole('button', { name: 'Подтвердить сопоставление' }).click()

  await workflow.getByLabel('Название, строка 1').fill(title)
  await workflow.getByLabel('Тип задачи, строка 1').selectOption('1')
  await workflow.getByLabel('Тип ответа, строка 1').selectOption('3')
  await workflow.getByLabel('Ошибка формата, строка 1').fill('Введите целое число, например -7')
  if (options.correctAnswer !== null) {
    await workflow.getByLabel('Правильный ответ, строка 1').fill(options.correctAnswer ?? '7')
  }
  await workflow.getByLabel('Неверный ответ, строка 1').fill('Нет, это другое число.')
  await workflow.getByLabel('Верный ответ, строка 1', { exact: true }).fill('Да, всё верно!')

  const metadataResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'PUT' &&
      new URL(response.url()).pathname ===
        `/staff/api/v1/group-lessons/${target.groupLessonPublicId}/metadata-grid`,
  )
  await workflow.getByRole('button', { name: 'Сохранить' }).click()
  expect((await metadataResponse).status()).toBe(200)
  await expect(workflow.getByText('Сопоставление и метаданные подтверждены.')).toBeVisible()

  await workflow.getByRole('button', { name: 'Опубликовать сейчас' }).click()
  const publicationResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname === '/staff/api/v1/publications',
  )
  await workflow.getByRole('button', { name: 'Подтвердить' }).click()
  expect((await publicationResponse).status()).toBe(201)
}

async function publishRepairedTestProblem(
  page: Page,
  target: SubmissionTarget,
  projectName: string,
  retry: number,
  existingTitle: string,
  sourceTitle: string,
  sourceItem: string,
): Promise<void> {
  const workflow = page.getByTestId('content-workflow-condition')
  await workflow.getByLabel('LaTeX-файл').setInputFiles({
    // A new immutable revision keeps the source-lineage filename stable.
    name: 'test-submission.tex',
    mimeType: 'application/x-tex',
    buffer: Buffer.from(
      testProblemSource(projectName, retry + 100, sourceTitle, sourceItem),
      'utf-8',
    ),
  })

  const uploadResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname === '/staff/api/v1/content/uploads',
  )
  await workflow.getByRole('button', { name: 'Загрузить и проверить' }).click()
  expect((await uploadResponse).status()).toBe(201)

  const matching = workflow.getByLabel('Сопоставление задачи 1')
  await expect(matching).toBeVisible()
  const existingValue = await matching
    .locator('option')
    .evaluateAll(
      (options, title) =>
        options
          .find(
            (option) =>
              /^(?:auto_position|manual_match):/.test(option.getAttribute('value') ?? '') &&
              option.textContent?.includes(String(title)),
          )
          ?.getAttribute('value'),
      existingTitle,
    )
  if (!existingValue) throw new Error(`No existing problem candidate for ${existingTitle}`)
  await matching.selectOption(existingValue)
  await workflow.getByRole('button', { name: 'Подтвердить сопоставление' }).click()

  await workflow.getByLabel('Правильный ответ, строка 1').fill('7')
  const metadataResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'PUT' &&
      new URL(response.url()).pathname ===
        `/staff/api/v1/group-lessons/${target.groupLessonPublicId}/metadata-grid`,
  )
  await workflow.getByRole('button', { name: 'Сохранить' }).click()
  expect((await metadataResponse).status()).toBe(200)
  await expect(workflow.getByText('Сопоставление и метаданные подтверждены.')).toBeVisible()

  await workflow.getByRole('button', { name: 'Опубликовать сейчас' }).click()
  const publicationResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname === '/staff/api/v1/publications',
  )
  await workflow.getByRole('button', { name: 'Подтвердить' }).click()
  expect((await publicationResponse).status()).toBe(201)
}

async function serverAttempts(page: Page, problemId: string) {
  return page.evaluate(async (id) => {
    const response = await fetch(`/student/api/v1/problems/${id}/test-attempts`)
    if (!response.ok) throw new Error(`Attempt history returned ${response.status}`)
    return (await response.json()) as {
      attempts: Array<{ displayAnswer: string; outcome: string }>
    }
  }, problemId)
}

test.beforeEach(async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
})

test('Phase 4: a test answer survives reload and an offline POST is delivered exactly once', async ({
  page,
}, testInfo) => {
  const target = targetForProject(testInfo.project.name)
  await loginThroughUi(page, AUTH_PERSONAS.admin, `/staff/lessons/${target.groupLessonPublicId}`)
  await publishTestProblem(page, target, testInfo.project.name, testInfo.retry)

  await loginThroughUi(page, AUTH_PERSONAS.student, '/student/tasks')
  await page.goto(
    `/student/tasks?course=${contentFixture.coursePublicId}` +
      `&group=${contentFixture.groupPublicId}&lesson=${target.lessonNumber}`,
  )
  const task = page.getByRole('button', {
    name: new RegExp(`Тестовая сдача ${testInfo.project.name}`),
  })
  await expect(task).toBeVisible()
  await task.click()
  await expect(page.getByRole('heading', { name: 'Тестовая сдача', exact: true })).toBeVisible()
  await expect(page.getByText('Ваш ответ')).toBeVisible()

  const attemptPath = /\/student\/api\/v1\/problems\/[^/]+\/test-attempts$/
  let submissionRequests = 0
  page.on('request', (request) => {
    if (request.method() === 'POST' && attemptPath.test(new URL(request.url()).pathname)) {
      submissionRequests += 1
    }
  })

  const answer = page.getByLabel('Ответ', { exact: true })
  await answer.fill('7жф')
  await page.getByRole('button', { name: 'Проверить' }).click()
  await expect(page.getByRole('alert')).toContainText('Введите целое число, например -7')
  expect(submissionRequests).toBe(0)

  await answer.fill('7')
  await page.reload()
  await expect(page.getByLabel('Ответ', { exact: true })).toHaveValue('7')

  const created = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' && attemptPath.test(new URL(response.url()).pathname),
  )
  await page.getByRole('button', { name: 'Проверить' }).click()
  expect((await created).status()).toBe(201)
  await expect(page.getByText('Да, ответ принят')).toBeVisible()
  await expect(page.getByText('Да, всё верно!')).toBeVisible()

  const problemId = new URL(page.url()).pathname.split('/').at(-1)
  if (!problemId) throw new Error('Student task URL has no problem identity')
  await expect.poll(async () => (await serverAttempts(page, problemId)).attempts.length).toBe(1)

  // Use the browser's real offline mode so the POST cannot leave the browser.
  // This exercises the production transport and durable outbox without MSW or
  // a fabricated HTTP response.
  await page.context().setOffline(true)
  try {
    await page.getByLabel('Ответ', { exact: true }).fill('8')
    await page.getByRole('button', { name: 'Проверить' }).click()
    await expect(page.getByText('Ответ сохранён в очереди')).toBeVisible()
  } finally {
    await page.context().setOffline(false)
  }

  await page.reload()
  await expect(page.getByText('Ответ сохранён в очереди')).toBeVisible()
  await expect(page.getByLabel('Ответ', { exact: true })).toHaveValue('8')
  expect((await serverAttempts(page, problemId)).attempts).toHaveLength(1)

  const retried = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' && attemptPath.test(new URL(response.url()).pathname),
  )
  await page.getByRole('button', { name: 'Повторить отправку' }).click()
  expect((await retried).status()).toBe(201)
  await expect(page.getByText('Ответ пока неверный')).toBeVisible()
  await expect(page.getByText('Нет, это другое число.')).toBeVisible()

  await expect.poll(async () => (await serverAttempts(page, problemId)).attempts.length).toBe(2)
  expect((await serverAttempts(page, problemId)).attempts).toEqual([
    expect.objectContaining({ displayAnswer: '8', outcome: 'wrong' }),
    expect.objectContaining({ displayAnswer: '7', outcome: 'correct' }),
  ])
})

test('Phase 4: an admin repairs a published checker and rechecks an immutable pending answer', async ({
  page,
}, testInfo) => {
  const target = targetForProject(testInfo.project.name)
  const title = `Отложенная проверка ${testInfo.project.name}`
  const sourceTitle = 'Отложенная проверка'
  const sourceItem = `pending-${testInfo.project.name}`
  await loginThroughUi(page, AUTH_PERSONAS.admin, `/staff/lessons/${target.groupLessonPublicId}`)
  await publishTestProblem(page, target, testInfo.project.name, testInfo.retry, {
    title,
    sourceTitle,
    sourceItem,
    correctAnswer: null,
  })

  await loginThroughUi(page, AUTH_PERSONAS.student, '/student/tasks')
  await page.goto(
    `/student/tasks?course=${contentFixture.coursePublicId}` +
      `&group=${contentFixture.groupPublicId}&lesson=${target.lessonNumber}`,
  )
  await page.getByRole('button', { name: new RegExp(title) }).click()
  const taskUrl = page.url()
  const problemId = new URL(taskUrl).pathname.split('/').at(-1)
  if (!problemId) throw new Error('Student task URL has no problem identity')

  await page.getByLabel('Ответ', { exact: true }).fill('7')
  const pendingResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname === `/student/api/v1/problems/${problemId}/test-attempts`,
  )
  await page.getByRole('button', { name: 'Проверить' }).click()
  expect((await pendingResponse).status()).toBe(201)
  await expect(page.getByText('Ответ сохранён и ждёт настройки')).toBeVisible()
  expect((await serverAttempts(page, problemId)).attempts).toEqual([
    expect.objectContaining({ displayAnswer: '7', outcome: 'pending_configuration' }),
  ])

  // The Staff cookie is audience-scoped and remains valid while the Student
  // session is active on the same production-like origin.
  await page.goto(`/staff/lessons/${target.groupLessonPublicId}`)
  await publishRepairedTestProblem(
    page,
    target,
    testInfo.project.name,
    testInfo.retry,
    title,
    sourceTitle,
    sourceItem,
  )
  await page.goto(`/staff/problems/${problemId}`)
  await expect(page.getByText('Ожидают: 1')).toBeVisible()

  const recheckResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname ===
        `/staff/api/v1/problems/${problemId}/recheck-test-attempts`,
  )
  await page.getByRole('button', { name: 'Перепроверить 1 ответ' }).click()
  expect((await recheckResponse).status()).toBe(200)
  await expect(page.getByText('Проверено 1 из 1')).toBeVisible()
  await expect(page.getByText('Нет ответов, ожидающих настройки')).toBeVisible()

  await page.goto(taskUrl)
  await expect(page.getByLabel('Последние ответы').getByText('верно')).toBeVisible()
  expect((await serverAttempts(page, problemId)).attempts).toEqual([
    expect.objectContaining({ displayAnswer: '7', outcome: 'correct' }),
  ])
})
