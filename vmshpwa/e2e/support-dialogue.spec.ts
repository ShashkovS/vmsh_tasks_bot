import path from 'node:path'
import { AUTH_PERSONAS, loginThroughUi } from './auth-personas'
import { studentCourseAccessResponseSchema } from '../packages/contracts/src/courses'
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
  await page
    .locator('input[type="file"][multiple]')
    .setInputFiles(path.resolve('../pwa_tests/fixtures/student-results-photo.webp'))
  await expect(page.getByAltText('Выбранная фотография')).toBeVisible()
  await expect(
    page.getByText('Черновик сохранён на этом устройстве.', { exact: true }),
  ).toBeVisible()
  await page.reload()
  await expect(page.getByAltText('Выбранная фотография')).toBeVisible()
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

  await expect(staffPage.locator('img[alt="Фотография 1"]')).toBeVisible()
  await expect
    .poll(() =>
      staffPage
        .locator('img[alt="Фотография 1"]')
        .evaluate((image: HTMLImageElement) => image.naturalWidth),
    )
    .toBeGreaterThan(0)
  for (const width of [320, 390]) {
    await page.setViewportSize({ width, height: 844 })
    await expect(page.getByRole('button', { name: 'Сделать фотографию' })).toBeVisible()
    await page.screenshot({
      path: testInfo.outputPath(`question-photos-${width}.png`),
      animations: 'disabled',
    })
  }
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

// docs/question-attention.md: real replies, archive jump and two independent devices.
test('new replies jump into an older worksheet and read state converges across devices', async ({
  page,
  context,
  secondaryContext,
}, testInfo) => {
  test.setTimeout(120_000)
  const lesson = ({ chromium: 32101, webkit: 32102, firefox: 32103 } as Record<string, number>)[
    testInfo.project.name
  ]!
  await loginThroughUi(
    page,
    AUTH_PERSONAS.student,
    `/student/tasks/math-5-7/${encodeURIComponent('н')}/${lesson}`,
  )
  const question = page.getByRole('region', { name: 'Обсуждение задачи' }).first()
  await question.getByRole('button', { name: /^(Задать вопрос|Вопросы по задаче)/ }).click()
  await question
    .getByRole('textbox', { name: 'Сообщение' })
    .fill(`Вопрос attention ${testInfo.project.name} ${testInfo.retry}`)
  const created = page.waitForResponse(
    (r) =>
      r.request().method() === 'POST' &&
      /\/student\/api\/v1\/questions(?:\/sup-\d+\/entries)?$/.test(new URL(r.url()).pathname),
  )
  await question.getByRole('button', { name: /^(Отправить вопрос|Дополнить вопрос)$/ }).click()
  const threadId = ((await (await created).json()) as { thread: { threadId: string } }).thread
    .threadId
  await expect(question.getByRole('button', { name: 'Дополнить вопрос', exact: true })).toBeVisible(
    { timeout: 15_000 },
  )
  await expect(question.getByRole('button', { name: /Ждём ответа преподавателя/ })).toBeVisible({
    timeout: 15_000,
  })
  await question.getByRole('button', { name: 'Скрыть вопросы' }).click()

  const access = studentCourseAccessResponseSchema.parse(
    await (await page.request.get('/student/api/v1/courses')).json(),
  )
  const contexts = access.enrollments.flatMap((enrollment) =>
    enrollment.allowedGroups.map((group) => ({ enrollment, group })),
  )
  const another =
    contexts.find(({ enrollment }) => enrollment.course.code !== 'math-5-7') ??
    contexts.find(({ group }) => group.code !== 'н')
  expect(another, 'Fixture must exercise switching course/group').toBeDefined()
  if (process.env.VMSH_E2E_SUPPORT_NAVIGATION === '1')
    expect(another!.enrollment.course.code).not.toBe('math-5-7')
  await page.goto(
    `/student/tasks?course=${encodeURIComponent(another!.enrollment.course.code)}&group=${encodeURIComponent(another!.group.code)}`,
  )
  const device = await secondaryContext.newPage()
  await loginThroughUi(device, AUTH_PERSONAS.student, '/student/tasks')
  const staff = await context.newPage()
  await loginThroughUi(staff, AUTH_PERSONAS.teacher, `/staff/questions/${threadId}`)
  const text = `Новый ответ attention ${testInfo.project.name} ${testInfo.retry}`
  await staff.getByRole('textbox', { name: 'Сообщение' }).fill(text)
  await staff.getByRole('button', { name: 'Ответить', exact: true }).click()
  await expect(page.getByRole('button', { name: /Новые ответы \(/ })).toBeVisible()
  await expect(device.getByRole('button', { name: /Новые ответы \(/ })).toBeVisible()
  await page.bringToFront()
  await page.getByRole('button', { name: /Новые ответы \(/ }).click()
  await expect(page).toHaveURL(new RegExp(`question=${threadId}`))
  await expect(page.getByText(text, { exact: true })).toBeInViewport()
  const targetQuestion = page
    .getByRole('region', { name: 'Обсуждение задачи' })
    .filter({ hasText: text })
  await expect(
    targetQuestion.getByRole('button', { name: /Есть непрочитанный ответ/ }),
  ).toBeVisible()
  await targetQuestion
    .getByRole('button', { name: /Есть непрочитанный ответ/ })
    .screenshot({ path: testInfo.outputPath('question-unread-indicator.png') })
  await targetQuestion
    .locator('..')
    .screenshot({ path: testInfo.outputPath('question-unread.png') })
  await expect(page.getByRole('button', { name: /Новые ответы \(/ })).toHaveCount(0, {
    timeout: 15_000,
  })
  await expect(device.getByRole('button', { name: /Новые ответы \(/ })).toHaveCount(0, {
    timeout: 15_000,
  })
  await expect(
    targetQuestion.getByRole('button', { name: /Есть непрочитанный ответ/ }),
  ).toHaveCount(0)
  await page.reload()
  await expect(page.getByText(text, { exact: true })).toBeInViewport()
  await page.setViewportSize({ width: 320, height: 800 })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.getByRole('button', { name: 'Переключить на тёмную тему' }).click()
  await expect(page.getByRole('button', { name: 'Переключить на светлую тему' })).toBeVisible()
  await targetQuestion.locator('..').scrollIntoViewIfNeeded()
  await targetQuestion
    .locator('..')
    .screenshot({ path: testInfo.outputPath('question-read-dark-320.png') })
  const localeHeaders = { Origin: new URL(page.url()).origin }
  const answerUrl = page.url()
  try {
    await page.goto('/student/profile', { waitUntil: 'domcontentloaded' })
    const profileUrl = page.url()
    const localeReload = page.waitForEvent('framenavigated', {
      predicate: (frame) => frame === page.mainFrame() && frame.url() === profileUrl,
    })
    await Promise.all([localeReload, page.getByRole('radio', { name: 'English' }).click()])
    await page.waitForLoadState('domcontentloaded')
    await expect(page.locator('html')).toHaveAttribute('lang', 'en')
    await page.goto(answerUrl, { waitUntil: 'domcontentloaded' })
    const englishQuestion = page
      .getByRole('region', { name: 'Problem discussion', exact: true })
      .filter({ hasText: text })
    await englishQuestion.getByRole('button', { name: 'Hide questions', exact: true }).click()
    await staff.getByRole('textbox', { name: 'Сообщение' }).fill(`${text} EN`)
    await staff.getByRole('button', { name: 'Ответить', exact: true }).click()
    await expect(page.getByRole('button', { name: /New replies \(/ })).toBeVisible()
    await page.getByRole('button', { name: /New replies \(/ }).click()
    await expect(page.getByText(`${text} EN`, { exact: true })).toBeInViewport()
    const unreadQuestion = page
      .getByRole('region', { name: 'Problem discussion', exact: true })
      .filter({ hasText: `${text} EN` })
    await expect(
      unreadQuestion.getByRole('button', { name: /There is an unread reply/ }),
    ).toBeVisible()
    await expect(unreadQuestion.locator('.bg-status-danger')).toHaveCSS('animation-name', 'none')
    await unreadQuestion
      .getByRole('button', { name: /There is an unread reply/ })
      .screenshot({ path: testInfo.outputPath('question-unread-en-indicator.png') })
    await unreadQuestion
      .locator('..')
      .screenshot({ path: testInfo.outputPath('question-unread-dark-en-reduced-320.png') })
    await expect(page.getByRole('button', { name: /New replies \(/ })).toHaveCount(0, {
      timeout: 15_000,
    })
  } finally {
    expect(
      (
        await page.request.put('/student/api/v1/auth/locale', {
          headers: localeHeaders,
          data: { locale: 'ru' },
        })
      ).status(),
    ).toBe(200)
  }
  await staff.close()
})
