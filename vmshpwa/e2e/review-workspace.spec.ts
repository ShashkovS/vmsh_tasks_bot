import { authContextSchema } from '../packages/contracts/src/auth'
import {
  familyWrittenThreadResponseSchema,
  writtenStudentReactionResponseSchema,
  writtenThreadResponseSchema,
} from '../packages/contracts/src/written-submissions'
import { AUTH_PERSONAS, loginThroughUi } from './auth-personas'
import { expect, test } from './fixtures'

test('Phase 6: Staff review restores its draft and completes one leased case', async ({
  page,
  secondaryContext,
}, testInfo) => {
  test.setTimeout(90_000)
  const project = testInfo.project.name
  const queueId = `e2e-review-queue-${project}`
  const title = `E2E проверка ${project}`

  await loginThroughUi(page, AUTH_PERSONAS.teacher, '/staff/review')
  const row = page.getByRole('row').filter({ hasText: title })
  await expect(row).toBeVisible()

  // A second Staff account keeps the queue open. Claim and completion must
  // update it through the audience-scoped queue invalidations, not polling.
  const adminPage = await secondaryContext.newPage()
  await loginThroughUi(adminPage, AUTH_PERSONAS.admin, '/staff/review')
  const adminRow = adminPage.getByRole('row').filter({ hasText: title })
  await expect(adminRow.getByRole('button', { name: 'Открыть' })).toBeVisible()

  await row.getByRole('button', { name: 'Открыть' }).click()
  await expect(page).toHaveURL(new RegExp(`/staff/review/${queueId}$`))
  await expect(adminRow).toContainText('Проверяет Преподаватель Тестовый')

  await expect(page.getByText('Поясните, почему этот переход верен.')).toBeVisible()
  await expect(
    page.getByText('Я дописал объяснение перехода и проверил крайний случай.'),
  ).toBeVisible()

  const drawing = page.getByRole('application', { name: 'Область разметки фотографии' })
  await expect(drawing).toBeVisible()
  await page.getByRole('button', { name: 'Прямоугольник' }).click()
  const bounds = await drawing.boundingBox()
  if (!bounds) throw new Error('Review annotation canvas has no visible bounds')
  await page.mouse.move(bounds.x + bounds.width * 0.2, bounds.y + bounds.height * 0.2)
  await page.mouse.down()
  await page.mouse.move(bounds.x + bounds.width * 0.65, bounds.y + bounds.height * 0.45)
  await page.mouse.up()
  await page.getByRole('button', { name: 'Повернуть по часовой стрелке' }).click()
  await expect(page.getByText('100% · 90° · 1 пометок')).toBeVisible()

  const comment = page.getByLabel('Комментарий')
  await comment.fill(`Проверено в ${project}; переход обоснован.`)
  const verdict = page.getByRole('button', { name: /В целом верно/ })
  await verdict.click()
  const reaction = page.getByRole('button', { name: /Суперское решение/ })
  await reaction.click()

  await page.reload()
  await expect(page.getByLabel('Комментарий')).toHaveValue(
    `Проверено в ${project}; переход обоснован.`,
  )
  await expect(page.getByRole('button', { name: /В целом верно/ })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await expect(page.getByRole('button', { name: /Суперское решение/ })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await expect(page.getByText('100% · 90° · 1 пометок')).toBeVisible()

  // Keep a linked Family session and an independently observable socket live
  // before completion. The product provider uses the same event to refetch
  // active TanStack queries; this socket makes owner routing explicit in E2E.
  const familyPage = await page.context().newPage()
  await loginThroughUi(familyPage, AUTH_PERSONAS.family, '/family/')
  await familyPage.evaluate(() => {
    const state = globalThis as typeof globalThis & {
      __reviewRealtimeEvents?: Array<Record<string, unknown>>
      __reviewRealtimeSocket?: WebSocket
    }
    state.__reviewRealtimeEvents = []
    const url = new URL('/family/ws', window.location.origin)
    url.protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const socket = new WebSocket(url)
    socket.addEventListener('message', (event) => {
      const payload: unknown = JSON.parse(String(event.data))
      if (payload && typeof payload === 'object' && !Array.isArray(payload)) {
        state.__reviewRealtimeEvents?.push(payload as Record<string, unknown>)
      }
    })
    state.__reviewRealtimeSocket = socket
  })
  await expect
    .poll(() =>
      familyPage.evaluate(() => {
        const state = globalThis as typeof globalThis & {
          __reviewRealtimeEvents?: Array<Record<string, unknown>>
        }
        return state.__reviewRealtimeEvents?.some((event) => event.type === 'connected') ?? false
      }),
    )
    .toBe(true)

  const completed = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname === `/staff/api/v1/review/items/${queueId}/complete`,
  )
  await page.getByRole('button', { name: 'Отправить вердикт' }).click()
  const completedResponse = await completed
  expect(completedResponse.status()).toBe(200)
  const receipt = (await completedResponse.json()) as {
    review: {
      annotations: Array<{
        attachmentId: string
        rotation: number
        markCount: number
      }>
    }
  }
  expect(receipt.review.annotations).toEqual([
    {
      annotationId: expect.any(String),
      attachmentId: `e2e-review-attachment-${project}`,
      schemaVersion: 1,
      rotation: 90,
      markCount: 1,
    },
  ])
  await expect(page).toHaveURL(/\/staff\/review\/?$/)
  await expect(page.getByRole('row').filter({ hasText: title })).toHaveCount(0)
  await expect(adminRow).toHaveCount(0)
  const teacherReactionInboxStatus = await page.evaluate(async () => {
    const response = await fetch('/staff/api/v1/review/reactions')
    return response.status
  })
  expect(teacherReactionInboxStatus).toBe(403)
  await adminPage.goto('/staff/reactions')
  await expect(adminPage.getByRole('heading', { name: 'Реакции и разногласия' })).toBeVisible()
  const teacherReactionItem = adminPage
    .getByRole('article')
    .filter({ hasText: title })
    .filter({ hasText: '🔥 Суперское решение.' })
  await expect(teacherReactionItem).toContainText(title)
  await expect(teacherReactionItem).toContainText('🔥 Суперское решение.')
  await expect
    .poll(() =>
      familyPage.evaluate((expectedResource) => {
        const state = globalThis as typeof globalThis & {
          __reviewRealtimeEvents?: Array<Record<string, unknown>>
        }
        const event = state.__reviewRealtimeEvents?.find(
          (candidate) =>
            candidate.type === 'invalidate' &&
            candidate.reason === 'written-review-completed' &&
            Array.isArray(candidate.resources) &&
            candidate.resources.includes(expectedResource),
        )
        if (!event) return null
        return {
          audience: event.audience,
          resources: event.resources,
          accountId: event.accountId ?? null,
        }
      }, `problems/e2e-review-problem-${project}/thread`),
    )
    .toEqual({
      audience: 'family',
      resources: [`problems/e2e-review-problem-${project}/thread`],
      accountId: null,
    })

  await loginThroughUi(page, AUTH_PERSONAS.student, '/student/')
  const studentProjection = await page.evaluate(async (problemId) => {
    const response = await fetch(`/student/api/v1/problems/${problemId}/thread`)
    const body: unknown = await response.json()
    return { status: response.status, body }
  }, `e2e-review-problem-${project}`)
  expect(studentProjection.status).toBe(200)
  const studentThread = writtenThreadResponseSchema.parse(studentProjection.body)
  expect(studentThread.thread?.reviews).toEqual([
    expect.objectContaining({
      verdict: 15,
      comment: `Проверено в ${project}; переход обоснован.`,
      source: 'staff',
      evidenceEntryIds: [`e2e-review-student-entry-${project}`],
      annotations: [
        expect.objectContaining({
          attachmentId: `e2e-review-attachment-${project}`,
          schemaVersion: 1,
          rotation: 90,
          marks: [expect.objectContaining({ kind: 'rectangle' })],
        }),
      ],
    }),
  ])
  expect(studentThread.thread?.reviews[0]).not.toHaveProperty('internalReaction')
  expect(studentThread.thread?.reviews[0]?.studentReaction).toBeNull()

  const reviewId = studentThread.thread?.reviews[0]?.reviewId
  if (!reviewId) throw new Error('Student review projection has no public review ID')
  const studentReactionMutation = await page.evaluate(async (reviewPublicId) => {
    const response = await fetch(`/student/api/v1/reviews/${reviewPublicId}/reaction`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ schemaVersion: 1, reactionId: 2, expectedVersion: 0 }),
    })
    const body: unknown = await response.json()
    return { status: response.status, body }
  }, reviewId)
  expect(studentReactionMutation.status).toBe(200)
  const studentReaction = writtenStudentReactionResponseSchema.parse(studentReactionMutation.body)
  expect(studentReaction.studentReaction).toEqual(
    expect.objectContaining({ reactionId: 2, version: 1, deleted: false }),
  )
  const updatedStudentProjection = await page.evaluate(async (problemId) => {
    const response = await fetch(`/student/api/v1/problems/${problemId}/thread`)
    const body: unknown = await response.json()
    return { status: response.status, body }
  }, `e2e-review-problem-${project}`)
  expect(updatedStudentProjection.status).toBe(200)
  expect(
    writtenThreadResponseSchema.parse(updatedStudentProjection.body).thread?.reviews[0]
      ?.studentReaction,
  ).toEqual(expect.objectContaining({ reactionId: 2, version: 1, deleted: false }))
  await expect
    .poll(() =>
      familyPage.evaluate((expectedResource) => {
        const state = globalThis as typeof globalThis & {
          __reviewRealtimeEvents?: Array<Record<string, unknown>>
        }
        const event = state.__reviewRealtimeEvents?.find(
          (candidate) =>
            candidate.type === 'invalidate' &&
            candidate.reason === 'written-review-student-reaction-changed' &&
            Array.isArray(candidate.resources) &&
            candidate.resources.includes(expectedResource),
        )
        if (!event) return null
        return { audience: event.audience, resources: event.resources }
      }, `problems/e2e-review-problem-${project}/thread`),
    )
    .toEqual({
      audience: 'family',
      resources: [`problems/e2e-review-problem-${project}/thread`],
    })

  const familyAuth = await familyPage.evaluate(async () => {
    const authResponse = await fetch('/family/api/v1/auth/me')
    const authBody: unknown = await authResponse.json()
    return { status: authResponse.status, body: authBody }
  })
  expect(familyAuth.status).toBe(200)
  const familyContext = authContextSchema.parse(familyAuth.body)
  if (familyContext.principal.audience !== 'family') {
    throw new Error('Family auth endpoint returned another audience')
  }
  const child = familyContext.principal.linkedChildren.find(
    (candidate) => candidate.studentId === 'user-student-online-fixture',
  )
  if (!child) throw new Error('Review student is not linked to the E2E family')
  const familyProjection = await familyPage.evaluate(
    async ({ problemId, studentId }) => {
      const threadResponse = await fetch(
        `/family/api/v1/children/${studentId}/problems/${problemId}/thread`,
      )
      const threadBody: unknown = await threadResponse.json()
      return {
        status: threadResponse.status,
        body: threadBody,
      }
    },
    { problemId: `e2e-review-problem-${project}`, studentId: child.studentId },
  )
  expect(familyProjection.status).toBe(200)
  const familyThread = familyWrittenThreadResponseSchema.parse(familyProjection.body)
  expect(familyThread.studentId).toBe('user-student-online-fixture')
  expect(familyThread.thread?.reviews).toEqual([
    expect.objectContaining({
      verdict: 15,
      comment: `Проверено в ${project}; переход обоснован.`,
      source: 'staff',
      evidenceEntryIds: [`e2e-review-student-entry-${project}`],
      annotations: [
        expect.objectContaining({
          attachmentId: `e2e-review-attachment-${project}`,
          schemaVersion: 1,
          rotation: 90,
          marks: [expect.objectContaining({ kind: 'rectangle' })],
        }),
      ],
      studentReaction: expect.objectContaining({
        reactionId: 2,
        version: 1,
        deleted: false,
      }),
    }),
  ])
  expect(familyThread.thread?.reviews[0]).not.toHaveProperty('internalReaction')
  const familyAttachment = familyThread.thread?.entries
    .flatMap((entry) => entry.attachments)
    .find((attachment) => attachment.attachmentId === `e2e-review-attachment-${project}`)
  expect(familyAttachment?.mediaPath).toBe(
    `/family/api/v1/children/user-student-online-fixture/thread-entries/e2e-review-student-entry-${project}/attachments/e2e-review-attachment-${project}/media`,
  )
  const familyMedia = await familyPage.evaluate(async (mediaPath) => {
    if (!mediaPath) throw new Error('Family projection has no submitted photo')
    const response = await fetch(mediaPath)
    return {
      status: response.status,
      contentType: response.headers.get('content-type'),
      bodySize: (await response.arrayBuffer()).byteLength,
    }
  }, familyAttachment?.mediaPath)
  expect(familyMedia).toEqual({
    status: 200,
    contentType: 'image/webp',
    bodySize: expect.any(Number),
  })
  expect(familyMedia.bodySize).toBeGreaterThan(0)

  const studentReactionItem = adminPage
    .getByRole('article')
    .filter({ hasText: title })
    .filter({ hasText: '🙋 Не могу согласиться с проверкой!' })
  await expect(studentReactionItem).toContainText(title)
  await expect(studentReactionItem).toContainText('🙋 Не могу согласиться с проверкой!')
  await expect(teacherReactionItem).toContainText(title)
  await expect(teacherReactionItem).toContainText('🔥 Суперское решение.')

  await studentReactionItem.getByRole('button', { name: 'Перепроверить результат' }).click()
  let correctionPanel = adminPage
    .locator('[aria-label^="Перепроверка:"]')
    .filter({ hasText: title })
  const correctedComment = `Перепроверено в ${project}: переход нужно довести.`
  await expect(
    correctionPanel.getByRole('img', { name: 'Страница 1 решения ученика' }),
  ).toBeVisible()
  await correctionPanel.getByLabel('Комментарий').fill(correctedComment)
  await correctionPanel.getByRole('button', { name: /Есть идеи, не доведено/ }).click()

  // The correction is a significant Staff draft: reload must not erase it.
  await adminPage.reload()
  await adminPage
    .getByRole('article')
    .filter({ hasText: title })
    .filter({ hasText: '🙋 Не могу согласиться с проверкой!' })
    .getByRole('button', { name: 'Перепроверить результат' })
    .click()
  correctionPanel = adminPage.locator('[aria-label^="Перепроверка:"]').filter({ hasText: title })
  await expect(correctionPanel.getByLabel('Комментарий')).toHaveValue(correctedComment)
  await expect(
    correctionPanel.getByRole('button', { name: /Есть идеи, не доведено/ }),
  ).toHaveAttribute('aria-pressed', 'true')

  const correctionResponse = adminPage.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname === `/staff/api/v1/reviews/${reviewId}/correction`,
  )
  await correctionPanel.getByRole('button', { name: 'Отправить вердикт' }).click()
  expect((await correctionResponse).status()).toBe(200)
  const staleStudentReactionItem = adminPage
    .getByRole('article')
    .filter({ hasText: title })
    .filter({ hasText: '🙋 Не могу согласиться с проверкой!' })
  await expect(staleStudentReactionItem).toContainText('Уже есть более новая проверка')
  await expect(
    staleStudentReactionItem.getByRole('button', { name: 'Перепроверить результат' }),
  ).toHaveCount(0)

  const correctedStudentProjection = await page.evaluate(async (problemId) => {
    const response = await fetch(`/student/api/v1/problems/${problemId}/thread`)
    const body: unknown = await response.json()
    return { status: response.status, body }
  }, `e2e-review-problem-${project}`)
  expect(correctedStudentProjection.status).toBe(200)
  const correctedStudentThread = writtenThreadResponseSchema.parse(correctedStudentProjection.body)
  expect(correctedStudentThread.thread?.status).toBe('needs_work')
  expect(correctedStudentThread.thread?.reviews).toHaveLength(2)
  expect(correctedStudentThread.thread?.reviews[1]).toEqual(
    expect.objectContaining({
      verdict: 13,
      comment: correctedComment,
      evidenceEntryIds: [`e2e-review-student-entry-${project}`],
      annotations: [],
    }),
  )

  const correctedFamilyProjection = await familyPage.evaluate(
    async ({ problemId, studentId }) => {
      const response = await fetch(
        `/family/api/v1/children/${studentId}/problems/${problemId}/thread`,
      )
      const body: unknown = await response.json()
      return { status: response.status, body }
    },
    { problemId: `e2e-review-problem-${project}`, studentId: child.studentId },
  )
  expect(correctedFamilyProjection.status).toBe(200)
  const correctedFamilyThread = familyWrittenThreadResponseSchema.parse(
    correctedFamilyProjection.body,
  )
  expect(correctedFamilyThread.thread?.status).toBe('needs_work')
  expect(correctedFamilyThread.thread?.reviews[1]).toEqual(
    expect.objectContaining({ verdict: 13, comment: correctedComment }),
  )
  await expect
    .poll(() =>
      familyPage.evaluate((expectedResource) => {
        const state = globalThis as typeof globalThis & {
          __reviewRealtimeEvents?: Array<Record<string, unknown>>
        }
        return (
          state.__reviewRealtimeEvents?.some(
            (candidate) =>
              candidate.type === 'invalidate' &&
              candidate.reason === 'written-review-corrected' &&
              Array.isArray(candidate.resources) &&
              candidate.resources.includes(expectedResource),
          ) ?? false
        )
      }, `problems/e2e-review-problem-${project}/thread`),
    )
    .toBe(true)

  await familyPage.evaluate(() => {
    const state = globalThis as typeof globalThis & { __reviewRealtimeSocket?: WebSocket }
    state.__reviewRealtimeSocket?.close()
  })
  await familyPage.close()
  await adminPage.close()
})
