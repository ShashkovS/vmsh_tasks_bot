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
