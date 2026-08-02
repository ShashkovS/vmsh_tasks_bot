import { randomUUID } from 'node:crypto'

import { AUTH_PERSONAS, loginThroughUi, type AuthPersona } from './auth-personas'
import { expect, test } from './fixtures'

test.setTimeout(90_000)

function classroomPersona(project: string, audience: 'student' | 'family'): AuthPersona {
  if (audience === 'student') {
    return {
      persona: 'student',
      accountPublicId: `account-classroom-e2e-${project}`,
      audience,
      username: `classroom-e2e-${project}`,
      credentialField: 'telegramToken',
      credential: AUTH_PERSONAS.student.credential,
    }
  }
  return {
    persona: 'family',
    accountPublicId: `account-classroom-family-e2e-${project}`,
    audience,
    username: `classroom-family-e2e-${project}`,
    credentialField: 'password',
    credential: AUTH_PERSONAS.family.credential,
  }
}

test('Phase 7: admin maintains the durable classroom catalog', async ({ page }, testInfo) => {
  const suffix = `${testInfo.project.name}-${randomUUID().slice(0, 8)}`
  const numberedRoom = `201 ${suffix}`
  const hall = `Актовый зал ${suffix}`
  const renamedHall = `Большой зал ${suffix}`

  await loginThroughUi(
    page,
    AUTH_PERSONAS.admin,
    '/staff/classrooms?tab=catalog&event=in-person-2026-02-01&roomStatus=active',
  )
  await expect(page.getByRole('heading', { name: 'Каталог аудиторий' })).toBeVisible()

  const createRoom = async (name: string, expectedStatus: number) => {
    await page.getByLabel('Новая аудитория').fill(`  ${name}  `)
    const response = page.waitForResponse(
      (candidate) =>
        candidate.request().method() === 'POST' &&
        new URL(candidate.url()).pathname === '/staff/api/v1/classrooms',
    )
    await page.getByRole('button', { name: 'Добавить' }).click()
    expect((await response).status()).toBe(expectedStatus)
  }

  await createRoom(numberedRoom, 201)
  await expect(page.getByText(numberedRoom, { exact: true })).toBeVisible()
  await createRoom(hall, 201)
  await expect(page.getByText(hall, { exact: true })).toBeVisible()

  await createRoom(hall.toLocaleUpperCase('ru'), 409)
  await expect(page.getByRole('alert')).toContainText('Такая аудитория уже есть')
  await expect(page.getByLabel('Новая аудитория')).toHaveValue(
    `  ${hall.toLocaleUpperCase('ru')}  `,
  )
  await page.getByRole('button', { name: 'Показать существующую' }).click()
  await expect(page.getByLabel('Поиск')).toHaveValue(hall)

  const hallRow = page.getByRole('listitem').filter({ hasText: hall })
  await hallRow.getByRole('button', { name: `Переименовать: ${hall}` }).click()
  await page.getByLabel(`Новое название: ${hall}`).fill(renamedHall)
  const renameResponse = page.waitForResponse(
    (candidate) =>
      candidate.request().method() === 'PATCH' &&
      new URL(candidate.url()).pathname.startsWith('/staff/api/v1/classrooms/'),
  )
  await page.getByRole('button', { name: 'Сохранить' }).click()
  expect((await renameResponse).status()).toBe(200)
  await page.getByLabel('Поиск').fill('')
  await page.getByLabel('Показывать').selectOption('active')
  await expect(page.getByText(renamedHall, { exact: true })).toBeVisible()

  const renamedRow = page.getByRole('listitem').filter({ hasText: renamedHall })
  const archiveResponse = page.waitForResponse((candidate) =>
    new URL(candidate.url()).pathname.endsWith('/archive'),
  )
  await renamedRow.getByRole('button', { name: 'Скрыть' }).click()
  expect((await archiveResponse).status()).toBe(200)
  await expect(renamedRow).toHaveCount(0)

  await page.getByLabel('Показывать').selectOption('archived')
  const archivedRow = page.getByRole('listitem').filter({ hasText: renamedHall })
  await expect(archivedRow).toBeVisible()
  const restoreResponse = page.waitForResponse((candidate) =>
    new URL(candidate.url()).pathname.endsWith('/restore'),
  )
  await archivedRow.getByRole('button', { name: 'Восстановить' }).click()
  expect((await restoreResponse).status()).toBe(200)
  await expect(archivedRow).toHaveCount(0)
})

test('Phase 7: an event layout survives reload and is confirmed explicitly', async ({
  page,
}, testInfo) => {
  const project = testInfo.project.name
  const eventPublicId = `in-person-classrooms-e2e-${project}`
  const roomNameByProject: Record<string, string> = {
    chromium: '201 E2E chromium',
    webkit: '202 E2E webkit',
    firefox: '203 E2E firefox',
  }
  const secondRoomNameByProject: Record<string, string> = {
    chromium: '202 E2E webkit',
    webkit: '203 E2E firefox',
    firefox: '201 E2E chromium',
  }
  const roomName = roomNameByProject[project]
  const secondRoomName = secondRoomNameByProject[project]
  const reassignRoomName = `Переназначение E2E ${project}`
  if (roomName === undefined || secondRoomName === undefined) {
    throw new Error(`Unknown Playwright project: ${project}`)
  }

  await loginThroughUi(
    page,
    AUTH_PERSONAS.admin,
    `/staff/classrooms?tab=groups&event=${eventPublicId}&roomStatus=active`,
  )
  await expect(page.getByRole('heading', { name: 'Аудитории по группам' })).toBeVisible()
  await expect(page.getByText('Унаследовано')).toBeVisible()

  await page.getByRole('button', { name: 'Изменить для занятия' }).click()
  await expect(page.getByText('Черновик')).toBeVisible()
  const groupLabel = `Математика 5–7 · Начинающие E2E ${project}`
  const roomSelect = page.getByLabel(`Группа для аудитории ${roomName}`)
  await roomSelect.selectOption({ label: groupLabel })
  await page
    .getByLabel(`Группа для аудитории ${secondRoomName}`)
    .selectOption({ label: groupLabel })
  await page
    .getByLabel(`Группа для аудитории ${reassignRoomName}`)
    .selectOption({ label: groupLabel })

  await page.reload()
  await expect(page.getByRole('heading', { name: 'Аудитории по группам' })).toBeVisible()
  await expect(page.getByLabel(`Группа для аудитории ${roomName}`)).toHaveValue(
    `group-lesson-classroom-e2e-${project}`,
  )
  await expect(page.getByLabel(`Группа для аудитории ${secondRoomName}`)).toHaveValue(
    `group-lesson-classroom-e2e-${project}`,
  )
  await expect(page.getByLabel(`Группа для аудитории ${reassignRoomName}`)).toHaveValue(
    `group-lesson-classroom-e2e-${project}`,
  )

  const saveResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'PUT' && new URL(response.url()).pathname.endsWith('/rooms'),
  )
  const confirmResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname.endsWith('/confirm'),
  )
  await page.getByRole('button', { name: 'Подтвердить схему' }).click()
  expect((await saveResponse).status()).toBe(200)
  expect((await confirmResponse).status()).toBe(200)
  await expect(page.getByText('Подтверждено')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Изменить схему' })).toBeVisible()
})

test('Phase 7: classroom edits survive reload and are explicitly announced', async ({
  page,
}, testInfo) => {
  const project = testInfo.project.name
  const eventPublicId = `in-person-classrooms-e2e-${project}`
  const studentName = `Тестов ${project} Ученик`
  const reassignRoomName = `Переназначение E2E ${project}`

  await loginThroughUi(
    page,
    AUTH_PERSONAS.admin,
    `/staff/classrooms?tab=catalog&event=${eventPublicId}&roomStatus=archived`,
  )
  const archivedFixtureRoom = page.getByRole('listitem').filter({ hasText: reassignRoomName })
  if ((await archivedFixtureRoom.count()) > 0) {
    const restoreResponse = page.waitForResponse((response) =>
      new URL(response.url()).pathname.endsWith('/restore'),
    )
    await archivedFixtureRoom.getByRole('button', { name: 'Восстановить' }).click()
    expect((await restoreResponse).status()).toBe(200)
  }
  await page.goto(`/staff/classrooms?tab=students&event=${eventPublicId}&roomStatus=active`)
  await expect(page.getByRole('heading', { name: 'Школьники по аудиториям' })).toBeVisible()

  const recalculateResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname.endsWith('/classroom-assignment-plan/recalculate'),
  )
  await page.getByRole('button', { name: 'Пересчитать' }).click()
  expect((await recalculateResponse).status()).toBe(200)
  await expect(page.getByText(studentName, { exact: true })).toBeVisible()

  const roomSelect = page.getByLabel(`Аудитория для ${studentName}`)
  const studentRow = roomSelect.locator('xpath=ancestor::li[1]')
  await expect(studentRow.getByText('возраст 13.6', { exact: true })).toBeVisible()
  await expect(studentRow.getByText('класс 7', { exact: true })).toBeVisible()
  await expect(studentRow.getByText('сила 8.0', { exact: true })).toBeVisible()
  const targetRoom = (
    await roomSelect.locator('option').evaluateAll((options) =>
      options.map((option) => ({
        value: (option as HTMLOptionElement).value,
        label: option.textContent?.trim() ?? '',
      })),
    )
  ).find((option) => option.label === reassignRoomName)
  if (targetRoom === undefined) throw new Error(`No alternate classroom for ${project}`)
  expect(await roomSelect.inputValue()).not.toBe(targetRoom.value)
  await roomSelect.selectOption(targetRoom.value)
  await page.reload()
  await expect(page.getByLabel(`Аудитория для ${studentName}`)).toHaveValue(targetRoom.value)

  const saveResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'PUT' &&
      new URL(response.url()).pathname.endsWith('/assignments'),
  )
  const confirmResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname.endsWith('/confirm'),
  )
  await page.getByRole('button', { name: 'Подтвердить план' }).click()
  expect((await saveResponse).status()).toBe(200)
  expect((await confirmResponse).status()).toBe(200)
  await expect(page.getByText('Подтверждено')).toBeVisible()
  await expect(page.getByLabel(`Аудитория для ${studentName}`)).toHaveValue(targetRoom.value)

  const historyResponse = page.waitForResponse((response) =>
    new URL(response.url()).pathname.endsWith('/history'),
  )
  await page.getByRole('button', { name: `История аудиторий: ${studentName}` }).click()
  expect((await historyResponse).status()).toBe(200)
  const history = page
    .getByRole('heading', { name: `История аудиторий: ${studentName}` })
    .locator('xpath=ancestor::section[1]')
  await expect(history).toContainText(targetRoom.label)

  // Phase 7 requires a separate explicit action after confirmation. The E2E
  // harness has no Telegram adapter, so this browser proof deliberately sends
  // only the PWA channel; Telegram transport has its own recording-adapter test.
  const previewResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname.endsWith('/delivery-preview'),
  )
  await page.getByRole('button', { name: 'Подготовить предпросмотр' }).click()
  expect((await previewResponse).status()).toBe(200)
  await expect(page.getByText('Получателей: 1', { exact: true })).toBeVisible()
  await expect(page.getByText('Без Telegram: 1', { exact: true })).toBeVisible()
  const telegram = page.getByRole('checkbox', { name: /Telegram/ })
  await expect(telegram).toBeChecked()
  await telegram.click()

  const deliveryResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname.endsWith('/delivery-batches'),
  )
  await page.getByRole('button', { name: 'Разослать аудитории' }).click()
  const sentDeliveryResponse = await deliveryResponse
  expect(sentDeliveryResponse.status()).toBe(201)
  const sentDelivery = (await sentDeliveryResponse.json()) as {
    batch: {
      deliveryReport: {
        channels: { pwa: { selected: number }; telegram: { selected: number } }
        deliveredAny: number
        deliveredAll: number
        partial: number
      }
    }
  }
  expect(sentDelivery.batch.deliveryReport).toMatchObject({
    channels: { pwa: { selected: 1 }, telegram: { selected: 0 } },
    deliveredAny: 1,
    deliveredAll: 1,
    partial: 0,
  })
  const deliveryReport = page.getByTestId('classroom-delivery-report')
  await expect(deliveryReport).toContainText('Получили хотя бы одно: 1')
  await expect(deliveryReport).toContainText('Получили всё: 1')
  await expect(deliveryReport).toContainText(/успешно\s*1/)

  const eventName = `E2E схема аудиторий ${project}`
  await loginThroughUi(page, classroomPersona(project, 'student'), '/student/')
  const studentEvent = page.getByText(eventName, { exact: false }).locator('xpath=..')
  await expect(studentEvent).toContainText(targetRoom.label)
  await expect(studentEvent).toContainText('Разослано')
  await page.goto('/student/profile/notifications')
  const classroomNotification = page
    .getByRole('link', { name: new RegExp(targetRoom.label) })
    .first()
  await expect(classroomNotification).toContainText('Назначена аудитория')
  await expect(classroomNotification).toContainText(targetRoom.label)

  await loginThroughUi(page, classroomPersona(project, 'family'), '/family/')
  const familyEvent = page.getByText(eventName, { exact: false }).locator('xpath=..')
  await expect(familyEvent).toContainText(targetRoom.label)
  await expect(familyEvent).toContainText('Разослано')
  const familyNotifications = await page.evaluate(async () => {
    const response = await fetch('/family/api/v1/notification-events')
    return { status: response.status, payload: (await response.json()) as { items: unknown[] } }
  })
  expect(familyNotifications.status).toBe(200)
  expect(
    familyNotifications.payload.items.some(
      (item) =>
        typeof item === 'object' &&
        item !== null &&
        'category' in item &&
        item.category === 'classroom_assignment',
    ),
  ).toBe(false)

  await page.goto(`/staff/classrooms?tab=catalog&event=${eventPublicId}&roomStatus=active`)
  await page.getByLabel('Поиск').fill(reassignRoomName)
  const archivedRoom = page.getByRole('listitem').filter({ hasText: reassignRoomName })
  const archiveResponse = page.waitForResponse((response) =>
    new URL(response.url()).pathname.endsWith('/archive'),
  )
  await archivedRoom.getByRole('button', { name: 'Скрыть' }).click()
  expect((await archiveResponse).status()).toBe(200)

  await page.goto('/student/')
  const reassigningStudentEvent = page.getByText(eventName, { exact: false }).locator('xpath=..')
  await expect(reassigningStudentEvent).toContainText('Аудитория переназначается')

  await page.goto('/family/')
  const reassigningFamilyEvent = page.getByText(eventName, { exact: false }).locator('xpath=..')
  await expect(reassigningFamilyEvent).toContainText('Аудитория переназначается')

  await page.goto(`/staff/classrooms?tab=students&event=${eventPublicId}&roomStatus=active`)
  await expect(page.getByText(studentName, { exact: true })).toBeVisible()
  await expect(page.getByText('Не распределены / переназначаются')).toBeVisible()
  const secondRecalculateResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname.endsWith('/classroom-assignment-plan/recalculate'),
  )
  await page.getByRole('button', { name: 'Пересчитать' }).click()
  expect((await secondRecalculateResponse).status()).toBe(200)
  const replacementSelect = page.getByLabel(`Аудитория для ${studentName}`)
  await expect(replacementSelect).not.toHaveValue('')
  const replacementRoom = await replacementSelect.locator('option:checked').textContent()
  if (!replacementRoom) throw new Error(`No replacement classroom for ${project}`)
  const replacementRoomName = replacementRoom.trim()
  expect(replacementRoomName).not.toBe(reassignRoomName)

  const secondConfirmResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname.endsWith('/confirm'),
  )
  await page.getByRole('button', { name: 'Подтвердить план' }).click()
  expect((await secondConfirmResponse).status()).toBe(200)

  const secondPreviewResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname.endsWith('/delivery-preview'),
  )
  await page.getByRole('button', { name: 'Подготовить предпросмотр' }).click()
  expect((await secondPreviewResponse).status()).toBe(200)
  const secondTelegram = page.getByRole('checkbox', { name: /Telegram/ })
  await expect(secondTelegram).toBeChecked()
  await secondTelegram.click()
  const secondDeliveryResponse = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname.endsWith('/delivery-batches'),
  )
  await page.getByRole('button', { name: 'Разослать аудитории' }).click()
  expect((await secondDeliveryResponse).status()).toBe(201)

  await page.goto('/student/')
  const reassignedStudentEvent = page.getByText(eventName, { exact: false }).locator('xpath=..')
  await expect(reassignedStudentEvent).toContainText(replacementRoomName)
  await expect(reassignedStudentEvent).toContainText('Разослано')

  await page.goto('/family/')
  const reassignedFamilyEvent = page.getByText(eventName, { exact: false }).locator('xpath=..')
  await expect(reassignedFamilyEvent).toContainText(replacementRoomName)
  await expect(reassignedFamilyEvent).toContainText('Разослано')
})
