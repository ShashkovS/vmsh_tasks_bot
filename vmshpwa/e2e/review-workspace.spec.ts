import { AUTH_PERSONAS, loginThroughUi } from './auth-personas'
import { expect, test } from './fixtures'

test('Phase 6: Staff review restores its draft and completes one leased case', async ({
  page,
}, testInfo) => {
  const project = testInfo.project.name
  const queueId = `e2e-review-queue-${project}`
  const title = `E2E проверка ${project}`

  await loginThroughUi(page, AUTH_PERSONAS.teacher, '/staff/review')
  const row = page.getByRole('row').filter({ hasText: title })
  await expect(row).toBeVisible()
  await row.getByRole('button', { name: 'Открыть' }).click()
  await expect(page).toHaveURL(new RegExp(`/staff/review/${queueId}$`))

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
})
