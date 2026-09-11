import { AUTH_PERSONAS, loginThroughUi } from './auth-personas'
import { expect, test } from './fixtures'

// docs/organizer-questions.md: home action and aligned admin section navigation.
test('Organizer entry points have responsive layouts', async ({ page }, info) => {
  const question = `Организационный вопрос для вёрстки ${info.project.name}`
  await loginThroughUi(page, AUTH_PERSONAS.family, '/family/')
  const entry = page.getByRole('link', { name: 'Задать вопрос организаторам', exact: true })
  await expect(entry).toBeVisible()
  for (const width of [1280, 320, 390]) {
    await page.setViewportSize({ width, height: 900 })
    await expect(entry).toBeInViewport()
    const box = await entry.boundingBox()
    expect(box!.height).toBeGreaterThanOrEqual(44)
    await page.screenshot({
      animations: 'disabled',
      path: info.outputPath(`family-home-${width}.png`),
    })
  }
  await entry.click()
  await page.getByLabel('Сообщение организаторам').fill(question)
  await page.getByRole('button', { name: 'Отправить', exact: true }).click()
  await expect(page).toHaveURL(/\/family\/organizers\/oq-\d+/)
  await loginThroughUi(page, AUTH_PERSONAS.admin, '/staff/questions?state=awaiting_staff')
  const sections = page.getByRole('navigation', { name: 'Разделы вопросов' })
  await expect(sections.getByRole('link', { name: 'Школьников' })).toHaveAttribute(
    'aria-current',
    'page',
  )
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.screenshot({
    animations: 'disabled',
    path: info.outputPath('staff-student-questions.png'),
  })
  await sections.getByRole('link', { name: /Организаторам/ }).click()
  await expect(page.getByRole('button').filter({ hasText: question })).toBeVisible()
  await expect(sections.getByRole('link', { name: /Организаторам/ })).toHaveAttribute(
    'aria-current',
    'page',
  )
  for (const width of [1280, 320, 390]) {
    await page.setViewportSize({ width, height: 900 })
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBe(true)
    await page.screenshot({
      animations: 'disabled',
      path: info.outputPath(`staff-organizers-${width}.png`),
    })
  }
  await page.getByRole('button', { name: 'Переключить на тёмную тему' }).click()
  await page.screenshot({
    animations: 'disabled',
    path: info.outputPath('staff-organizers-dark.png'),
  })
})
