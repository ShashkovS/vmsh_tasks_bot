import { AUTH_PERSONAS, loginThroughUi } from './auth-personas'
import { expect, test } from './fixtures'

test.setTimeout(90_000)

function reviewFixtureId(project: string): number {
  const fixtureIds: Record<string, number> = {
    chromium: 9701,
    webkit: 9702,
    firefox: 9703,
  }
  const fixtureId = fixtureIds[project]
  if (fixtureId === undefined) throw new Error(`Unknown Playwright project: ${project}`)
  return fixtureId
}

test('Phase 6: private Student and Staff dialogue survives reload and syncs live', async ({
  page,
  secondaryContext,
}, testInfo) => {
  const project = testInfo.project.name
  const fixtureId = reviewFixtureId(project)
  const groupLessonId = `gl-${fixtureId}`
  const problemId = `p-${fixtureId}`
  const composePath =
    `/student/questions/new?groupLesson=${groupLessonId}` + `&problem=${problemId}`
  const studentQuestion = `Почему здесь нужен этот переход? ${project}, ${testInfo.retry}`
  const staffReply = `Потому что сохраняется чётность. Ответ из ${project}.`
  const studentFollowUp = `Спасибо, теперь переход понятен. ${project}.`

  await loginThroughUi(page, AUTH_PERSONAS.student, composePath)
  await expect(page.getByRole('heading', { name: 'Спросить преподавателя' })).toBeVisible()

  const studentComposer = page.getByLabel('Сообщение')
  await studentComposer.fill(studentQuestion)
  await expect(
    page.getByText('Черновик сохранён на этом устройстве.', { exact: true }),
  ).toBeVisible()
  await page.reload()
  await expect(page.getByLabel('Сообщение')).toHaveValue(studentQuestion)

  const createResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname === '/student/api/v1/questions',
  )
  await page.getByRole('button', { name: 'Отправить' }).click()
  expect((await createResponse).status()).toBe(200)
  await expect(page).toHaveURL(/\/student\/questions\/sup-\d+$/)
  const threadId = new URL(page.url()).pathname.split('/').at(-1)
  if (!threadId) throw new Error('Created support dialogue has no public thread ID')
  await expect(page.getByText(studentQuestion, { exact: true })).toBeVisible()

  const staffPage = await secondaryContext.newPage()
  await loginThroughUi(staffPage, AUTH_PERSONAS.teacher, '/staff/questions?state=awaiting_staff')
  const questionLink = staffPage.getByRole('link').filter({ hasText: studentQuestion })
  await expect(questionLink).toBeVisible()
  await questionLink.click()
  await expect(staffPage).toHaveURL(`/staff/questions/${threadId}`)
  await expect(staffPage.getByText(studentQuestion, { exact: true })).toBeVisible()

  const staffComposer = staffPage.getByLabel('Сообщение')
  await staffComposer.fill(staffReply)
  await expect(
    staffPage.getByText('Черновик сохранён на этом устройстве.', { exact: true }),
  ).toBeVisible()
  await staffPage.reload()
  await expect(staffPage.getByLabel('Сообщение')).toHaveValue(staffReply)

  const staffResponse = staffPage.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname === `/staff/api/v1/questions/${threadId}/entries`,
  )
  await staffPage.getByRole('button', { name: 'Ответить' }).click()
  expect((await staffResponse).status()).toBe(200)
  await expect(staffPage.getByLabel('Сообщение')).toHaveValue('')
  await expect(page.getByText(staffReply, { exact: true })).toBeVisible()

  const followUpResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname === `/student/api/v1/questions/${threadId}/entries`,
  )
  await page.getByLabel('Сообщение').fill(studentFollowUp)
  await page.getByRole('button', { name: 'Дополнить вопрос' }).click()
  expect((await followUpResponse).status()).toBe(200)
  await expect(staffPage.getByText(studentFollowUp, { exact: true })).toBeVisible()

  await loginThroughUi(staffPage, AUTH_PERSONAS.studentInPerson, '/student/questions')
  await expect(staffPage.getByRole('heading', { name: 'Ваши вопросы' })).toBeVisible()
  await expect(staffPage.getByText(studentQuestion, { exact: true })).toHaveCount(0)
  await expect(staffPage.getByText('Вопросов пока нет')).toBeVisible()
})
