import { AUTH_PERSONAS, loginThroughUi } from './auth-personas'
import { expect, test } from './fixtures'

test('Phase 9: Family switches children and opens only their current course context', async ({
  page,
}) => {
  await loginThroughUi(page, AUTH_PERSONAS.family, '/family/children')
  await expect(page.getByRole('heading', { name: 'Дети' })).toBeVisible()
  await expect(page.getByText('Алексей Тестовый-Онлайн')).toBeVisible()
  await expect(page.getByText('Мария Тестовая-Очно')).toBeVisible()

  await page
    .getByText('Алексей Тестовый-Онлайн')
    .locator('xpath=../../..')
    .getByRole('button', { name: 'Открыть' })
    .click()
  await expect(page).toHaveURL(/\/family\/children\/user-student-online-fixture$/)
  await expect(page.getByRole('heading', { name: 'Алексей Тестовый-Онлайн' })).toBeVisible()
  await expect(page.getByText('Занятие 923 · Устная E2E firefox')).toBeVisible()
  await expect(page.getByText(/\d+ зачтено из \d+ задач/).first()).toBeVisible()
  await page.getByRole('button', { name: 'Открыть листок' }).click()
  await expect(page.getByText('Устная E2E firefox', { exact: true })).toBeVisible()

  await page.goto('/family/children')
  await page
    .getByText('Мария Тестовая-Очно')
    .locator('xpath=../../..')
    .getByRole('button', { name: 'Открыть' })
    .click()
  await expect(page.getByText('Новое занятие пока не опубликовано')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Открыть листок' })).toHaveCount(0)

  await page.goto('/family/children/unlinked-student')
  await expect(page.getByText('Этот профиль не связан с вашей учётной записью.')).toBeVisible()
})
