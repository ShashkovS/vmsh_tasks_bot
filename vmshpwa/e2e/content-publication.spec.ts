import contentFixture from '../../pwa_tests/fixtures/content/e2e-content-v1.json' with { type: 'json' }

import { AUTH_PERSONAS, loginThroughUi } from './auth-personas'
import { expect, test, type Page } from './fixtures'

test.setTimeout(90_000)

type ContentTarget = (typeof contentFixture.targets)[number]

function targetForProject(projectName: string): ContentTarget {
  const target = contentFixture.targets.find((candidate) => candidate.project === projectName)
  if (!target) throw new Error(`No Phase-2 content target for Playwright project ${projectName}`)
  return target
}

function latexSource(title: string, statement: string): string {
  return String.raw`\documentclass{article}
\begin{document}
\problem[name=e2e,title=${title}]
${statement}
\eproblem
\end{document}
`
}

async function uploadReviewAndPublish({
  page,
  target,
  source,
  metadataTitle,
  match,
}: {
  page: Page
  target: ContentTarget
  source: string
  metadataTitle: string
  match: 'insert-new' | 'suggested'
}): Promise<string> {
  const workflow = page.getByTestId('content-workflow-condition')
  await expect(workflow).toBeVisible()

  await workflow.getByLabel('LaTeX-файл').setInputFiles({
    name: 'condition.tex',
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
  if (match === 'insert-new') {
    await matching.selectOption('insert_new')
  } else {
    await matching.selectOption({ index: 1 })
    await expect(matching).toHaveValue(/^(auto_position|manual_match):/)
  }
  await workflow.getByRole('button', { name: 'Подтвердить сопоставление' }).click()

  const title = workflow.getByLabel('Название, строка 1')
  await title.fill(metadataTitle)
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
  })
  await expect(workflow.getByText(`Публичная revision: ${uploadPayload.revisionId}`)).toBeVisible()
  return uploadPayload.revisionId
}

test.beforeEach(async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
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
  await expect(workflow.getByLabel('Revision для отката')).toContainText('Revision 1')

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
})
