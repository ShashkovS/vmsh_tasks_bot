import { AUTH_PERSONAS, loginThroughUi, type AuthPersona } from './auth-personas'
import { expect, test } from './fixtures'

function phase9FamilyPersona(project: string): AuthPersona {
  return {
    persona: 'family',
    accountPublicId: `account-classroom-family-e2e-${project}`,
    audience: 'family',
    username: `classroom-family-e2e-${project}`,
    credentialField: 'password',
    credential: AUTH_PERSONAS.family.credential,
  }
}

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

test('Phase 9: child caches stay separate and Family confirms a group and mode change', async ({
  page,
}, testInfo) => {
  const project = testInfo.project.name
  const firstChild = `Ученик Тестов ${project}`
  const secondChild = `Второй Ребёнок ${project}`
  const secondChildId = `student-family-second-e2e-${project}`
  await loginThroughUi(page, phase9FamilyPersona(project), '/family/children')

  const initialEnrollment = await page.evaluate(async (studentId) => {
    const response = await fetch(`/family/api/v1/children/${studentId}/courses`)
    return (
      (await response.json()) as {
        enrollments: Array<{ activeGroupId: string; attendanceMode: string; version: number }>
      }
    ).enrollments[0]!
  }, `student-classroom-e2e-${project}`)
  const targetGroup =
    initialEnrollment.activeGroupId === 'group-fixture-beginner'
      ? 'group-fixture-continuing'
      : 'group-fixture-beginner'
  const targetMode = initialEnrollment.attendanceMode === 'online' ? 'in_person' : 'online'

  await page
    .getByText(firstChild, { exact: true })
    .locator('xpath=../../..')
    .getByRole('button', { name: 'Открыть' })
    .click()
  await expect(page.getByRole('heading', { name: firstChild })).toBeVisible()
  await expect(page.getByText('7 класс', { exact: true })).toBeVisible()

  let releaseSecondChild: () => void = () => {}
  const secondChildMayLoad = new Promise<void>((resolve) => {
    releaseSecondChild = resolve
  })
  const secondHome = `**/family/api/v1/children/${secondChildId}/home`
  await page.route(secondHome, async (route) => {
    await secondChildMayLoad
    await route.continue()
  })
  await page.goto('/family/children')
  await page
    .getByText(secondChild, { exact: true })
    .locator('xpath=../../..')
    .getByRole('button', { name: 'Открыть' })
    .click()
  await expect(page.getByRole('heading', { name: secondChild })).toBeVisible()
  await expect(page.getByText(firstChild, { exact: true })).toHaveCount(0)
  await expect(page.getByText('7 класс', { exact: true })).toHaveCount(0)
  releaseSecondChild()
  await expect(page.getByText('5 класс', { exact: true })).toBeVisible()
  await expect(page.getByText('Новое занятие пока не опубликовано')).toBeVisible()
  await page.unroute(secondHome)

  await page.goto(`/family/children/student-classroom-e2e-${project}`)
  await expect(page.getByRole('heading', { name: firstChild })).toBeVisible()
  await page.getByLabel('Группа').selectOption(targetGroup)
  await page.getByLabel('Формат занятий').selectOption(targetMode)
  await page.getByRole('button', { name: 'Изменить' }).click()
  await expect(page.getByText(/организаторы резервируют место/)).toBeVisible()

  const saved = page.waitForResponse(
    (response) =>
      response.request().method() === 'PATCH' &&
      new URL(response.url()).pathname.endsWith('/course-fixture-math-5-7/enrollment'),
  )
  await page.getByRole('button', { name: 'Подтвердить изменения' }).click()
  expect((await saved).status()).toBe(200)
  await expect(page.getByLabel('Группа')).toHaveValue(targetGroup)
  await expect(page.getByLabel('Формат занятий')).toHaveValue(targetMode)

  await page.reload()
  await expect(page.getByRole('heading', { name: firstChild })).toBeVisible()
  await expect(page.getByLabel('Группа')).toHaveValue(targetGroup)
  await expect(page.getByLabel('Формат занятий')).toHaveValue(targetMode)
  const enrollment = await page.evaluate(async (studentId) => {
    const response = await fetch(`/family/api/v1/children/${studentId}/courses`)
    return (await response.json()) as {
      enrollments: Array<{ activeGroupId: string; attendanceMode: string; version: number }>
    }
  }, `student-classroom-e2e-${project}`)
  expect(enrollment.enrollments[0]).toMatchObject({
    activeGroupId: targetGroup,
    attendanceMode: targetMode,
    version: initialEnrollment.version + 1,
  })
})
