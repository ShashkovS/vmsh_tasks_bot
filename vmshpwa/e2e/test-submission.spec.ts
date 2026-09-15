import { writtenThreadResponseSchema } from '../packages/contracts/src/written-submissions'
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

function readableLessonUrl(lessonNumber: number): string {
  return `/student/tasks/math-5-7/${encodeURIComponent('н')}/${lessonNumber}`
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
    problemType?: '1' | '2' | '3' | '4'
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
  const manualMatchingRequired = await matching
    .waitFor({ state: 'visible', timeout: 1_000 })
    .then(() => true)
    .catch(() => false)
  if (manualMatchingRequired) {
    await matching.selectOption('insert_new')
    await workflow.getByRole('button', { name: 'Подтвердить сопоставление' }).click()
  }

  await workflow.getByLabel('Название, строка 1').fill(title)
  const problemType = options.problemType ?? '1'
  await workflow.getByLabel('Тип задачи, строка 1').selectOption(problemType)
  if (problemType === '1') {
    await workflow.getByLabel('Тип ответа, строка 1').selectOption('3')
    await workflow.getByLabel('Ошибка формата, строка 1').fill('Введите целое число, например -7')
    if (options.correctAnswer !== null) {
      await workflow.getByLabel('Правильный ответ, строка 1').fill(options.correctAnswer ?? '7')
    }
    await workflow.getByLabel('Неверный ответ, строка 1').fill('Нет, это другое число.')
    await workflow.getByLabel('Верный ответ, строка 1', { exact: true }).fill('Да, всё верно!')
  }

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
  const manualMatchingRequired = await matching
    .waitFor({ state: 'visible', timeout: 1_000 })
    .then(() => true)
    .catch(() => false)
  if (manualMatchingRequired) {
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
  }

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

async function publishedProblemId(page: Page, target: SubmissionTarget, sourceItem: string) {
  return page.evaluate(
    async ({ courseId, groupLessonId, displayNumber }) => {
      const response = await fetch(
        `/student/api/v1/courses/${encodeURIComponent(courseId)}/lessons/${encodeURIComponent(groupLessonId)}/problems`,
      )
      if (!response.ok) throw new Error(`Published problems returned ${response.status}`)
      const body = (await response.json()) as {
        problems: Array<{ displayNumber: string; problemId: string }>
      }
      const problem = body.problems.find((candidate) => candidate.displayNumber === displayNumber)
      if (!problem) throw new Error(`Published problem ${displayNumber} is missing`)
      return problem.problemId
    },
    {
      courseId: contentFixture.coursePublicId,
      groupLessonId: target.groupLessonPublicId,
      displayNumber: `1${sourceItem}`,
    },
  )
}

async function openPublishedTestProblem(page: Page, sourceItem: string) {
  await page.getByRole('button', { name: `Открыть задачу 1${sourceItem}` }).click()
}

test.beforeEach(async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
})

test('Phase 4: a test answer survives reload and an offline POST is delivered exactly once', async ({
  page,
}, testInfo) => {
  const target = targetForProject(testInfo.project.name)
  const sourceItem = `e2e-${testInfo.retry}`
  await loginThroughUi(page, AUTH_PERSONAS.admin, `/staff/lessons/${target.groupLessonPublicId}`)
  await publishTestProblem(page, target, testInfo.project.name, testInfo.retry, { sourceItem })

  await loginThroughUi(page, AUTH_PERSONAS.student, '/student/tasks')
  await page.goto(readableLessonUrl(target.lessonNumber))
  await openPublishedTestProblem(page, sourceItem)
  await expect(page.getByRole('region', { name: 'Ваш ответ' })).toBeVisible()

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
  await expect(page.getByText('Да, всё верно!')).toBeVisible()

  const problemId = await publishedProblemId(page, target, sourceItem)
  await expect.poll(async () => (await serverAttempts(page, problemId)).attempts.length).toBe(1)

  // Use the browser's real offline mode so the POST cannot leave the browser.
  // This exercises the production transport and durable outbox without MSW or
  // a fabricated HTTP response.
  await page.context().setOffline(true)
  try {
    await page.getByLabel('Ответ', { exact: true }).fill('8')
    await page.getByRole('button', { name: 'Проверить' }).click()
    await expect(page.getByText('Отправим, когда появится сеть.')).toBeVisible()
  } finally {
    await page.context().setOffline(false)
  }

  await page.reload()
  await expect(page.getByText('Отправим, когда появится сеть.')).toBeVisible()
  expect((await serverAttempts(page, problemId)).attempts).toHaveLength(1)

  const retried = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' && attemptPath.test(new URL(response.url()).pathname),
  )
  await page.getByRole('button', { name: 'Повторить' }).click()
  expect((await retried).status()).toBe(201)
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
  const sourceItem = `pending-${testInfo.project.name}-${testInfo.retry}`
  await loginThroughUi(page, AUTH_PERSONAS.admin, `/staff/lessons/${target.groupLessonPublicId}`)
  await publishTestProblem(page, target, testInfo.project.name, testInfo.retry, {
    title,
    sourceTitle,
    sourceItem,
    correctAnswer: null,
  })

  await loginThroughUi(page, AUTH_PERSONAS.student, '/student/tasks')
  await page.goto(readableLessonUrl(target.lessonNumber))
  await openPublishedTestProblem(page, sourceItem)
  const taskUrl = page.url()
  const problemId = await publishedProblemId(page, target, sourceItem)

  await page.getByLabel('Ответ', { exact: true }).fill('7')
  const pendingResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname === `/student/api/v1/problems/${problemId}/test-attempts`,
  )
  await page.getByRole('button', { name: 'Проверить' }).click()
  expect((await pendingResponse).status()).toBe(201)
  await expect(page.getByText('Ответ принят и ожидает настройки проверки.')).toBeVisible()
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
  await expect(page.getByText('Ответов: 1')).toBeVisible()

  const recheckResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname ===
        `/staff/api/v1/problems/${problemId}/recheck-test-attempts`,
  )
  await page.getByRole('button', { name: 'Перепроверить 1 ответ' }).click()
  expect((await recheckResponse).status()).toBe(200)
  await expect(page.getByText('Проверено 1 из 1')).toBeVisible()

  await page.goto(taskUrl)
  await expect(
    page.getByRole('region', { name: 'Ваш ответ' }).getByText('Да, ответ принят.'),
  ).toBeVisible()
  expect((await serverAttempts(page, problemId)).attempts).toEqual([
    expect.objectContaining({ displayAnswer: '7', outcome: 'correct' }),
  ])
})

test('Phase 5: a written draft with a photo survives reload and resumes exactly once', async ({
  page,
}, testInfo) => {
  const target = targetForProject(testInfo.project.name)
  const title = `Письменная сдача ${testInfo.project.name}`
  const sourceItem = `written-${testInfo.project.name}-${testInfo.retry}`
  await loginThroughUi(page, AUTH_PERSONAS.admin, `/staff/lessons/${target.groupLessonPublicId}`)
  await publishTestProblem(page, target, testInfo.project.name, testInfo.retry, {
    title,
    sourceTitle: title,
    sourceItem,
    problemType: '2',
  })

  await loginThroughUi(page, AUTH_PERSONAS.student, '/student/tasks')
  await page.goto(readableLessonUrl(target.lessonNumber))
  await openPublishedTestProblem(page, sourceItem)
  await expect(page.getByRole('region', { name: 'Сдать решение' })).toBeVisible()

  const problemId = await publishedProblemId(page, target, sourceItem)

  const solutionText = 'Провёл дополнительную диагональ и получил два равных треугольника.'
  await page.getByLabel('Ваше решение').fill(solutionText)
  await page.locator('input[type="file"][multiple]').setInputFiles({
    name: 'page.png',
    mimeType: 'image/png',
    buffer: Buffer.from(
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
      'base64',
    ),
  })
  await expect(page.getByText('готово', { exact: true })).toBeVisible({ timeout: 30_000 })

  await page.reload()
  await expect(page.getByLabel('Ваше решение')).toHaveValue(solutionText)
  await expect(page.getByText('готово', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Страница 1: повернуть' })).toHaveCount(0)

  const writeCounts = { create: 0, upload: 0, reorder: 0, submit: 0 }
  page.on('request', (request) => {
    const pathname = new URL(request.url()).pathname
    if (request.method() === 'POST' && pathname.endsWith('/thread/entries')) {
      writeCounts.create += 1
    } else if (request.method() === 'POST' && pathname.endsWith('/attachments')) {
      writeCounts.upload += 1
    } else if (request.method() === 'PATCH' && pathname.endsWith('/attachments/order')) {
      writeCounts.reorder += 1
    } else if (request.method() === 'POST' && pathname.endsWith('/submit')) {
      writeCounts.submit += 1
    }
  })

  await page.context().setOffline(true)
  // Wait for the application-level connectivity state, not only the
  // Playwright network switch, before enqueueing the offline draft.
  await expect(page.getByText('Нет сети — отправим позже.')).toBeVisible()
  // The written composer always keeps its primary action named "Отправить";
  // submit() enqueues locally while navigator is offline.
  await page.getByRole('button', { name: 'Отправить' }).click()
  await expect(page.getByText('Отправим, когда появится сеть.')).toBeVisible()
  await expect(page.getByLabel('Ваше решение')).toHaveCount(0)
  expect(writeCounts).toEqual({ create: 0, upload: 0, reorder: 0, submit: 0 })

  const submitted = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname.endsWith('/submit'),
  )
  await page.context().setOffline(false)

  // A reconnect may start delivery before the hydrated outbox renders its
  // retry affordance.  If it did not, resume the durable queue explicitly.
  const retry = page.getByRole('button', { name: 'Повторить' })
  const edit = page.getByRole('button', { name: 'Изменить' })
  await expect
    .poll(async () => (await retry.isVisible()) || (await edit.isVisible()), { timeout: 30_000 })
    .toBe(true)
  if (await retry.isVisible()) await retry.click()
  expect((await submitted).status()).toBe(200)

  await expect(page.getByRole('button', { name: 'Изменить' })).toBeVisible()
  await expect(page.getByLabel('Ваше решение')).toHaveValue('')
  expect(writeCounts).toEqual({ create: 1, upload: 1, reorder: 0, submit: 1 })

  const persisted = await page.evaluate(async (id) => {
    const response = await fetch(`/student/api/v1/problems/${id}/thread`)
    if (!response.ok) throw new Error(`Written thread returned ${response.status}`)
    return (await response.json()) as {
      thread: null | {
        status: string
        entries: Array<{
          state: string
          text: string | null
          attachments: Array<{ mediaType: string; width: number; height: number }>
        }>
      }
    }
  }, problemId)
  expect(persisted.thread).toMatchObject({
    status: 'awaiting_review',
    entries: [
      {
        state: 'submitted',
        text: solutionText,
        attachments: [{ mediaType: 'image/webp', width: 1, height: 1 }],
      },
    ],
  })

  // Phase 5 permits an atomic pre-review correction: the accepted version is
  // copied into a durable local draft, then replaced as one server operation.
  const mediaResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'GET' && new URL(response.url()).pathname.endsWith('/media'),
  )
  page.once('dialog', (dialog) => void dialog.accept())
  await page.getByRole('button', { name: 'Изменить' }).click()
  expect((await mediaResponse).status()).toBe(200)
  await expect(
    page.getByText('Изменяете отправленное решение — оно заменится одной операцией.'),
  ).toBeVisible()
  await expect(page.getByLabel('Ваше решение')).toHaveValue(solutionText)
  await expect(
    page
      .getByRole('region', { name: 'Изменить решение' })
      .getByRole('img', { name: 'Страница 1' })
      .last(),
  ).toBeVisible()

  const replacementText = `${solutionText} Исправил обоснование равенства углов.`
  await page.getByLabel('Ваше решение').fill(replacementText)
  await page.reload()
  await expect(
    page.getByText('Изменяете отправленное решение — оно заменится одной операцией.'),
  ).toBeVisible()
  await expect(page.getByLabel('Ваше решение')).toHaveValue(replacementText)
  await expect(
    page
      .getByRole('region', { name: 'Изменить решение' })
      .getByRole('img', { name: 'Страница 1' })
      .last(),
  ).toBeVisible()

  const replaceResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname.endsWith('/replace'),
  )
  page.once('dialog', (dialog) => void dialog.accept())
  await page.getByRole('button', { name: 'Отправить', exact: true }).click()
  expect((await replaceResponse).status()).toBe(200)

  const replaced = await page.evaluate(async (id) => {
    const response = await fetch(`/student/api/v1/problems/${id}/thread`)
    if (!response.ok) throw new Error(`Written thread returned ${response.status}`)
    return (await response.json()) as {
      thread: null | {
        status: string
        entries: Array<{
          state: string
          text: string | null
          attachments: Array<{ mediaType: string; width: number; height: number }>
        }>
      }
    }
  }, problemId)
  expect(replaced.thread).toMatchObject({
    status: 'awaiting_review',
    entries: [
      {
        state: 'deleted',
        text: solutionText,
        attachments: [{ mediaType: 'image/webp', width: 1, height: 1 }],
      },
      {
        state: 'submitted',
        text: replacementText,
        attachments: [{ mediaType: 'image/webp', width: 1, height: 1 }],
      },
    ],
  })

  // docs/written-replacement-recovery.md: the teacher finishes while a replacement is drafted.
  const studentUrl = page.url()
  await expect(page.getByRole('button', { name: 'Изменить', exact: true })).toBeVisible()
  page.once('dialog', (dialog) => void dialog.accept())
  await page.getByRole('button', { name: 'Изменить', exact: true }).click()
  await expect(page.getByLabel('Ваше решение')).toHaveValue(replacementText)
  await expect(page.getByText('Копируем прежнее решение…')).toHaveCount(0)

  // Phase 6 handoff is part of the submission commit: the existing Staff
  // session sees one review case without a compatibility import or page seed.
  await page.goto('/staff/review')
  await page.getByRole('button', { name: 'Все работы', exact: true }).click()
  const reviewRow = page.getByRole('row').filter({ hasText: title })
  await expect(reviewRow).toHaveCount(1)
  await expect(reviewRow.getByRole('button', { name: 'Открыть' })).toBeVisible()
  await reviewRow.getByRole('button', { name: 'Открыть' }).click()
  await page.getByLabel('Комментарий').fill('Проверка во время подготовки исправления')
  await page.getByRole('button', { name: /В целом верно/ }).click()
  const completed = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname.endsWith('/complete'),
  )
  await page.getByRole('button', { name: 'Отправить вердикт' }).click()
  expect((await completed).status()).toBe(200)
  await page.goto(studentUrl)
  await expect(page.getByRole('button', { name: 'Изменить', exact: true })).toHaveCount(0)
  await expect(page.getByLabel('Ваше решение')).toHaveValue(replacementText)
  const rejected = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname.endsWith('/replace'),
  )
  page.once('dialog', (dialog) => void dialog.accept())
  await page.getByRole('button', { name: 'Отправить', exact: true }).click()
  expect((await rejected).status()).toBe(409)
  const recover = page.getByRole('button', { name: 'Отправить новым сообщением' })
  await expect(recover).toBeVisible()
  await page.reload()
  await expect(recover).toBeVisible()
  for (const width of [320, 390]) {
    await page.setViewportSize({ width, height: 844 })
    await recover.scrollIntoViewIfNeeded()
    await expect(recover).toBeInViewport()
    await page.screenshot({ path: testInfo.outputPath(`replacement-recovery-${width}.png`) })
  }
  const recoveredResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname.endsWith('/submit'),
  )
  await recover.click()
  expect((await recoveredResponse).status()).toBe(200)
  await expect(recover).toHaveCount(0)
  const history = writtenThreadResponseSchema.parse(
    await page.evaluate(async (id) => {
      const response = await fetch(`/student/api/v1/problems/${id}/thread`)
      return (await response.json()) as unknown
    }, problemId),
  ).thread!
  expect(history.reviews).toHaveLength(1)
  expect(
    history.entries.filter(
      (entry: { state: string; authorKind: string }) =>
        ['submitted', 'locked'].includes(entry.state) && entry.authorKind === 'student',
    ),
  ).toHaveLength(2)
  expect(history.entries.at(-1)).toMatchObject({
    text: replacementText,
    attachments: [{ mediaType: 'image/webp' }],
  })
})
