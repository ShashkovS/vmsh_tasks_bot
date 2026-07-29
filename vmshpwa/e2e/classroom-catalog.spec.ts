import { randomUUID } from 'node:crypto'

import { AUTH_PERSONAS, loginThroughUi } from './auth-personas'
import { expect, test } from './fixtures'

test.setTimeout(90_000)

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
  const roomSelect = page.getByLabel(`Группа для аудитории ${roomName}`)
  await roomSelect.selectOption({ label: 'Математика 5–7 · Начинающие' })
  await page
    .getByLabel(`Группа для аудитории ${secondRoomName}`)
    .selectOption({ label: 'Математика 5–7 · Начинающие' })

  await page.reload()
  await expect(page.getByRole('heading', { name: 'Аудитории по группам' })).toBeVisible()
  await expect(page.getByLabel(`Группа для аудитории ${roomName}`)).toHaveValue(
    `group-lesson-content-e2e-${project}`,
  )
  await expect(page.getByLabel(`Группа для аудитории ${secondRoomName}`)).toHaveValue(
    `group-lesson-content-e2e-${project}`,
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

test('Phase 7: classroom student edits survive reload until explicit confirmation', async ({
  page,
}, testInfo) => {
  const project = testInfo.project.name
  const eventPublicId = `in-person-classrooms-e2e-${project}`
  const targetRoomByProject: Record<string, string> = {
    chromium: 'classroom-e2e-webkit',
    webkit: 'classroom-e2e-firefox',
    firefox: 'classroom-e2e-firefox',
  }
  const targetRoomNameByProject: Record<string, string> = {
    chromium: '202 E2E webkit',
    webkit: '203 E2E firefox',
    firefox: '203 E2E firefox',
  }
  const targetRoom = targetRoomByProject[project]
  const targetRoomName = targetRoomNameByProject[project]
  if (targetRoom === undefined || targetRoomName === undefined) {
    throw new Error(`Unknown Playwright project: ${project}`)
  }
  const studentName = `Тестов ${project} Ученик`

  await loginThroughUi(
    page,
    AUTH_PERSONAS.admin,
    `/staff/classrooms?tab=students&event=${eventPublicId}&roomStatus=active`,
  )
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
  await roomSelect.selectOption(targetRoom)
  await page.reload()
  await expect(page.getByLabel(`Аудитория для ${studentName}`)).toHaveValue(targetRoom)

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
  await expect(page.getByLabel(`Аудитория для ${studentName}`)).toHaveValue(targetRoom)

  const historyResponse = page.waitForResponse((response) =>
    new URL(response.url()).pathname.endsWith('/history'),
  )
  await page.getByRole('button', { name: `История аудиторий: ${studentName}` }).click()
  expect((await historyResponse).status()).toBe(200)
  const history = page
    .getByRole('heading', { name: `История аудиторий: ${studentName}` })
    .locator('xpath=ancestor::section[1]')
  await expect(history).toContainText(targetRoomName)
})
