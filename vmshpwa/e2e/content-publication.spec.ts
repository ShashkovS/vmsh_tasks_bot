import contentFixture from '../../pwa_tests/fixtures/content/e2e-content-v1.json' with { type: 'json' }

import { AUTH_PERSONAS, loginThroughUi } from './auth-personas'
import { expect, test, type Page } from './fixtures'

test.setTimeout(90_000)

type ContentTarget = (typeof contentFixture.targets)[number]
type ContentKind = 'condition' | 'hint' | 'solution'

function targetForProject(projectName: string): ContentTarget {
  const target = contentFixture.targets.find((candidate) => candidate.project === projectName)
  if (!target) throw new Error(`No Phase-2 content target for Playwright project ${projectName}`)
  return target
}

function latexSource(title: string, statement: string, kind: ContentKind = 'condition'): string {
  const problemStatement =
    kind === 'condition'
      ? String.raw`\объявление
Обычное объявление для E2E.
\кобъявление
${statement}
\важноеОбъявление
Важное объявление для E2E.
\кважноеОбъявление`
      : 'Условие для сопоставления.'
  const trailingMaterial =
    kind === 'hint'
      ? String.raw`
\hint ${statement} \ehint`
      : kind === 'solution'
        ? String.raw`
\solution ${statement} \esolution`
        : ''
  return String.raw`\documentclass{article}
\begin{document}
\problem[name=e2e,title=${title}]
${problemStatement}
\eproblem
${trailingMaterial}
\end{document}
`
}

async function uploadReviewAndPublish({
  page,
  target,
  source,
  metadataTitle,
  match,
  kind = 'condition',
}: {
  page: Page
  target: ContentTarget
  source: string
  metadataTitle?: string
  match: 'insert-new' | 'suggested'
  kind?: ContentKind
}): Promise<string> {
  const workflow = page.getByTestId(`content-workflow-${kind}`)
  await expect(workflow).toBeVisible()

  await workflow.getByLabel('LaTeX-файл').setInputFiles({
    name: `${kind}.tex`,
    mimeType: 'application/x-tex',
    buffer: Buffer.from(source, 'utf-8'),
  })
  const uploadResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname === '/staff/api/v1/content/uploads',
  )
  await workflow.getByRole('button', { name: 'Загрузить и проверить' }).click()
  const uploadResponse = await uploadResponsePromise
  expect(uploadResponse.status()).toBe(201)
  const uploadPayload = (await uploadResponse.json()) as { revisionId: string }
  expect(uploadPayload.revisionId).toMatch(/^content-revision-/)

  const matching = workflow.getByLabel('Сопоставление задачи 1')
  if (kind === 'condition') {
    await expect(workflow.getByText('Обычное объявление для E2E.', { exact: true })).toBeVisible()
    await expect(workflow.getByText('Важное объявление для E2E.', { exact: true })).toBeVisible()
    await expect(workflow.getByText('Важно', { exact: true })).toBeVisible()
  }
  if (match === 'insert-new') {
    await matching.selectOption('insert_new')
  } else {
    await matching.selectOption({ index: 1 })
    await expect(matching).toHaveValue(/^(auto_position|manual_match):/)
  }
  await workflow.getByRole('button', { name: 'Подтвердить сопоставление' }).click()

  if (kind === 'condition') {
    if (!metadataTitle) throw new Error('Condition publication requires a task title')
    const title = workflow.getByLabel('Название, строка 1')
    await title.fill(metadataTitle)
    // Phase 10 no-loss boundary: the real Staff route must restore the exact
    // account/revision-scoped grid before any server mutation is attempted.
    await page.reload()
    await expect(workflow.getByLabel('Название, строка 1')).toHaveValue(metadataTitle)
    const metadataResponsePromise = page.waitForResponse(
      (response) =>
        response.request().method() === 'PUT' &&
        new URL(response.url()).pathname ===
          `/staff/api/v1/group-lessons/${target.groupLessonPublicId}/metadata-grid`,
    )
    await workflow.getByRole('button', { name: 'Сохранить' }).click()
    const metadataResponse = await metadataResponsePromise
    expect(metadataResponse.status()).toBe(200)
    await expect(workflow.getByText('Сопоставление и метаданные подтверждены.')).toBeVisible()
    const remainingDraftKeys = await page.evaluate(
      ({ lessonId, revisionId }) => {
        const suffix = `:metadata:v1:${lessonId}:${revisionId}`
        return Object.keys(window.localStorage).filter((key) => key.endsWith(suffix))
      },
      { lessonId: target.groupLessonPublicId, revisionId: uploadPayload.revisionId },
    )
    expect(remainingDraftKeys).toEqual([])
  } else {
    await expect(
      workflow.getByText('Сопоставление задач подтверждено; метаданные берутся из условия.'),
    ).toBeVisible()
  }

  // Phase 2 publication contract: an explicit confirmation changes only the
  // selected concrete group-lesson revision; upload/review never auto-publish.
  await workflow.getByRole('button', { name: 'Опубликовать сейчас' }).click()
  const publicationResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname === '/staff/api/v1/publications',
  )
  await workflow.getByRole('button', { name: 'Подтвердить' }).click()
  const publicationResponse = await publicationResponsePromise
  expect(publicationResponse.status()).toBe(201)
  const publication = (await publicationResponse.json()) as {
    groupLessonId: string
    revisionId: string
  }
  expect(publication).toMatchObject({
    groupLessonId: target.groupLessonPublicId,
    revisionId: uploadPayload.revisionId,
    kind,
  })
  await expect(workflow.getByText(`Публичная revision: ${uploadPayload.revisionId}`)).toBeVisible()
  return uploadPayload.revisionId
}

test.beforeEach(async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
})

test('Deploy-first: Admin creates a lesson, changes its phases, publishes a solution and closes submissions', async ({
  page,
}, testInfo) => {
  const target = targetForProject(testInfo.project.name)
  const projectOffset = target.lessonNumber - 900
  const lessonNumber = 1_900 + projectOffset + testInfo.retry * 100
  const lessonTitle = `Приёмка полного цикла ${testInfo.project.name}`
  const taskTitle = `Задача полного цикла ${testInfo.project.name}`
  const solutionText = `Решение полного цикла для ${testInfo.project.name}.`

  await loginThroughUi(page, AUTH_PERSONAS.admin, '/staff/lessons')
  await page.getByRole('button', { name: 'Создать занятие' }).click()
  await page.getByLabel('Курс').selectOption(contentFixture.coursePublicId)
  await page.getByLabel('Группа').selectOption(contentFixture.groupPublicId)
  await page.getByLabel('Номер занятия').fill(String(lessonNumber))
  await page.getByLabel('Название (необязательно)').fill(lessonTitle)
  await page.getByLabel('Дата занятия').fill(`2027-02-0${projectOffset}`)
  await page.getByLabel('Открыть приём · Москва (необязательно)').fill('2026-01-01T16:00')
  await page.getByLabel('Закрыть приём · Москва').fill('2027-02-08T20:50')
  await page.getByLabel('Подсказки · Москва (необязательно)').fill('2027-02-06T12:00')
  await page.getByLabel('Решения · Москва (необязательно)').fill('2027-02-08T21:00')

  const createdResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname === '/staff/api/v1/group-lessons',
  )
  await page.getByRole('button', { name: 'Создать и открыть' }).click()
  const created = await createdResponse
  expect(created.status()).toBe(201)
  const createdPayload = (await created.json()) as {
    groupLesson: { groupLessonId: string; lessonNumber: number }
  }
  expect(createdPayload.groupLesson.lessonNumber).toBe(lessonNumber)
  const groupLessonId = createdPayload.groupLesson.groupLessonId
  await expect(page).toHaveURL(
    new RegExp(`/staff/lessons/${groupLessonId.replaceAll('.', '\\.')}$`),
  )

  await page.getByLabel('Открыть приём', { exact: true }).fill('2026-01-02T16:00')
  await page.getByLabel('Подсказки', { exact: true }).fill('2027-02-07T12:00')
  await page.getByLabel('Решения', { exact: true }).fill('2027-02-09T21:00')
  const scheduleResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'PATCH' &&
      new URL(response.url()).pathname.endsWith('/lesson-window/schedule'),
  )
  await page.getByRole('button', { name: 'Сохранить расписание публикаций' }).click()
  expect((await scheduleResponse).status()).toBe(200)

  await page.getByLabel('Дедлайн сдачи').fill('2027-02-09T20:50')
  const cutoffResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'PATCH' &&
      new URL(response.url()).pathname.endsWith('/lesson-window/submission-cutoff'),
  )
  await page.getByRole('button', { name: 'Изменить дедлайн' }).click()
  expect((await cutoffResponse).status()).toBe(200)

  const createdTarget = { ...target, groupLessonPublicId: groupLessonId, lessonNumber }
  await uploadReviewAndPublish({
    page,
    target: createdTarget,
    source: latexSource('Полный цикл', 'Условие задачи полного цикла.'),
    metadataTitle: taskTitle,
    match: 'insert-new',
  })
  await uploadReviewAndPublish({
    page,
    target: createdTarget,
    source: latexSource('Полный цикл', solutionText, 'solution'),
    match: 'suggested',
    kind: 'solution',
  })

  const closeResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'PATCH' &&
      new URL(response.url()).pathname.endsWith('/lesson-window/submission-cutoff'),
  )
  await page.getByRole('button', { name: 'Закрыть приём сейчас' }).click()
  const closed = await closeResponse
  expect(closed.status()).toBe(200)
  const closedPayload = (await closed.json()) as { submissionClosesAt: string }
  expect(new Date(closedPayload.submissionClosesAt).getTime()).toBeLessThanOrEqual(
    Date.now() + 5_000,
  )

  await loginThroughUi(page, AUTH_PERSONAS.student, '/student/tasks')
  await page.goto(
    `/student/tasks?course=${contentFixture.coursePublicId}` +
      `&group=${contentFixture.groupPublicId}&lesson=${lessonNumber}`,
  )
  await page.getByRole('button', { name: new RegExp(taskTitle) }).click()
  await page.getByRole('button', { name: /^Решение/ }).click()
  const revealResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      /\/reveal\/solution$/.test(new URL(response.url()).pathname),
  )
  await page.getByRole('button', { name: 'Показать решение' }).click()
  expect((await revealResponse).status()).toBe(200)
  await expect(page.getByText(solutionText)).toBeVisible()
})

test('Phase 2: Staff publishes two real revisions, Student reads them, then rollback restores the first', async ({
  page,
}, testInfo) => {
  const target = targetForProject(testInfo.project.name)
  const staffUrl = `/staff/lessons/${target.groupLessonPublicId}`
  const studentUrl =
    `/student/tasks/content-e2e?groupLesson=${target.groupLessonPublicId}` +
    '&material=condition&problem=1'

  // Acceptance trace: development-plan/06-phase-2-content.md; real routes are
  // Staff /content/uploads→compile→problem-matches→metadata-grid→publications
  // and Student /group-lessons/:id/content/condition, without MSW.
  await loginThroughUi(page, AUTH_PERSONAS.admin, staffUrl)
  await expect(page.getByRole('heading', { name: 'LaTeX и публикации' })).toBeVisible()

  const attempt = `${testInfo.project.name}, запуск ${testInfo.retry + 1}`
  const firstStatement = `Первая опубликованная версия для ${attempt}.`
  const firstTaskTitle = `Первая E2E-задача, запуск ${testInfo.retry + 1}`
  const firstRevisionId = await uploadReviewAndPublish({
    page,
    target,
    source: latexSource('Первая версия', firstStatement),
    metadataTitle: firstTaskTitle,
    match: testInfo.retry === 0 ? 'insert-new' : 'suggested',
  })
  const hintStatement = `Аудируемая подсказка для ${attempt}.`
  await uploadReviewAndPublish({
    page,
    target,
    source: latexSource('Первая версия', hintStatement, 'hint'),
    match: 'suggested',
    kind: 'hint',
  })

  await loginThroughUi(page, AUTH_PERSONAS.student, '/student/')
  await expect(page.getByRole('heading', { name: 'Сейчас', exact: true })).toBeVisible()
  await expect(page.getByText('Математика 5–7', { exact: true })).toBeVisible()
  await expect(page.getByText('1 задача в листке')).toBeVisible()

  await page.goto(
    `/student/tasks?course=${contentFixture.coursePublicId}&group=${contentFixture.groupPublicId}`,
  )
  await expect(page.getByRole('heading', { name: 'Задачи', exact: true })).toBeVisible()
  const lessonSelect = page.getByRole('combobox', { name: 'Занятие' })
  await expect(lessonSelect).toContainText(`${target.lessonNumber} ·`)
  await lessonSelect.selectOption(String(target.lessonNumber))
  await expect(page).toHaveURL(new RegExp(`[?&]lesson=${target.lessonNumber}(?:&|$)`))
  const taskRow = page.getByRole('button', { name: new RegExp(firstTaskTitle) })
  await expect(taskRow).toContainText('Не начата')
  await taskRow.click()
  await expect(page).toHaveURL(/\/student\/tasks\/problem-[0-9a-f]{32}\?/)
  await expect(page.getByText(firstStatement)).toBeVisible()
  await expect(page.getByText('Обычное объявление для E2E.')).toBeVisible()
  await expect(page.getByText('Важное объявление для E2E.')).toBeVisible()
  await expect(page.getByText('Важно', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: /^Подсказка/ }).click()
  const revealResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      /\/student\/api\/v1\/group-lessons\/[^/]+\/problems\/[^/]+\/reveal\/hint$/.test(
        new URL(response.url()).pathname,
      ),
  )
  await page.getByRole('button', { name: 'Показать подсказку' }).click()
  const revealResponse = await revealResponsePromise
  expect(revealResponse.status()).toBe(200)
  expect(await revealResponse.json()).toMatchObject({ firstReveal: true, kind: 'hint' })
  await expect(page.getByText(hintStatement)).toBeVisible()

  await page.reload()
  await page.getByRole('button', { name: /^Подсказка/ }).click()
  await expect(page.getByRole('button', { name: 'Показать подсказку' })).toHaveCount(0)
  await expect(page.getByText(hintStatement)).toBeVisible()

  // Phase 3 cold-offline checkpoint: after a full application reload there is
  // no in-memory Query cache, and every Student API request is disconnected.
  // The precached shell still loads under its real Service Worker. The
  // secret-free auth snapshot unlocks only this account's validated Dexie
  // records; a reveal is reusable only because the successful audited POST
  // above was cached. Playwright's context-wide offline mode rejects a cached
  // navigation in Firefox/WebKit before their Service Worker can answer it,
  // so the application API boundary returns the browser's native network
  // failure instead. This is not an HTTP mock: no response is manufactured.
  await page.waitForFunction(() => navigator.serviceWorker.controller !== null)
  const offlineMarker = 'vmsh-e2e-student-api-offline'
  await page.addInitScript((marker) => {
    const nativeFetch = window.fetch.bind(window)
    window.fetch = (input, init) => {
      const rawUrl = typeof input === 'string' || input instanceof URL ? String(input) : input.url
      const url = new URL(rawUrl, window.location.href)
      if (
        window.sessionStorage.getItem(marker) === '1' &&
        url.pathname.startsWith('/student/api/')
      ) {
        return Promise.reject(new TypeError('Failed to fetch'))
      }
      return nativeFetch(input, init)
    }
  }, offlineMarker)
  await page.evaluate((marker) => window.sessionStorage.setItem(marker, '1'), offlineMarker)
  try {
    await page.reload()
    await expect(page.getByText(/Показана последняя сохранённая копия/)).toBeVisible()
    await expect(page.getByText(firstStatement)).toBeVisible()
    await page.getByRole('button', { name: /^Подсказка/ }).click()
    await expect(page.getByRole('button', { name: 'Показать подсказку' })).toHaveCount(0)
    await expect(page.getByText(hintStatement)).toBeVisible()
  } finally {
    await page.evaluate((marker) => window.sessionStorage.removeItem(marker), offlineMarker)
  }
  await page.reload()
  // Firefox aborts a second navigation while the authenticated shell is still
  // completing its post-offline route reconciliation. Waiting for the actual
  // online document proves recovery and gives the router a stable boundary;
  // see development-plan/07-phase-3-offline-and-pwa.md.
  await expect(page.getByText(firstStatement)).toBeVisible()

  await page.goto(studentUrl)
  await expect(page.getByText(firstStatement)).toBeVisible()

  await page.goto(staffUrl)
  const secondStatement = `Вторая опубликованная версия для ${attempt}.`
  const secondRevisionId = await uploadReviewAndPublish({
    page,
    target,
    source: latexSource('Вторая версия', secondStatement),
    metadataTitle: `Вторая E2E-задача, запуск ${testInfo.retry + 1}`,
    match: 'suggested',
  })
  expect(secondRevisionId).not.toBe(firstRevisionId)

  await page.goto(studentUrl)
  await expect(page.getByText(secondStatement)).toBeVisible()
  await expect(page.getByText(firstStatement)).toHaveCount(0)

  await page.goto(staffUrl)
  const workflow = page.getByTestId('content-workflow-condition')
  await expect(workflow.getByText(`Публичная revision: ${secondRevisionId}`)).toBeVisible()
  await expect(workflow.getByLabel('Revision для отката')).toBeVisible()

  await workflow.getByRole('button', { name: 'Откатить опубликованное' }).click()
  const rollbackResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname.endsWith('/rollback'),
  )
  await workflow.getByRole('button', { name: 'Подтвердить' }).click()
  const rollbackResponse = await rollbackResponsePromise
  expect(rollbackResponse.status()).toBe(201)
  const rollback = (await rollbackResponse.json()) as { revisionId: string }
  expect(rollback.revisionId).toBe(firstRevisionId)
  await expect(workflow.getByText(`Публичная revision: ${firstRevisionId}`)).toBeVisible()

  await page.goto(studentUrl)
  await expect(page.getByText(firstStatement)).toBeVisible()
  await expect(page.getByText(secondStatement)).toHaveCount(0)

  // Account-isolation checkpoint: bypass the local provider for the server
  // logout so an old-owner cache really exists until the next login performs
  // its atomic owner switch. The second Student can authenticate normally but
  // cannot read the first Student's condition when the API then disappears.
  const logoutStatus = await page.evaluate(async () => {
    const response = await fetch('/student/api/v1/auth/logout', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    })
    return response.status
  })
  expect(logoutStatus).toBe(204)
  await loginThroughUi(page, AUTH_PERSONAS.studentInPerson, '/student/')
  await page.evaluate((marker) => window.sessionStorage.setItem(marker, '1'), offlineMarker)
  try {
    await page.goto(studentUrl)
    await expect(page.getByRole('heading', { name: 'Нет сети' })).toBeVisible()
    await expect(page.getByText(firstStatement)).toHaveCount(0)
    await expect(page.getByText(hintStatement)).toHaveCount(0)
  } finally {
    await page.evaluate((marker) => window.sessionStorage.removeItem(marker), offlineMarker)
  }
})
