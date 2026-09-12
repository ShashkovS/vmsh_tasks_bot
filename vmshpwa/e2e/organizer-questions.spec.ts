import path from 'node:path'
import { AUTH_PERSONAS, loginThroughUi } from './auth-personas'
import { expect, test } from './fixtures'

// docs/organizer-questions.md: real account privacy, photo drafts and live replies.
for (const audience of ['student', 'family'] as const) {
  test(`Organizers: ${audience} asks privately and administrator replies`, async ({
    page,
    context,
    secondaryContext,
  }, info) => {
    test.setTimeout(120_000)
    const question = `Вопрос организаторам ${audience} ${info.project.name} ${info.retry}`
    const reply = `Ответ организаторов ${audience} ${info.project.name}`
    await loginThroughUi(page, AUTH_PERSONAS[audience], `/${audience}/`)
    await page.getByRole('link', { name: 'Задать вопрос организаторам' }).click()
    const composer = page.getByLabel('Сообщение организаторам')
    await expect(composer).toBeEnabled()
    await composer.fill(question)
    if (audience === 'family') await expect(page.getByLabel('О ком вопрос')).toHaveValue('')
    await page
      .getByLabel('Прикрепить фотографии')
      .setInputFiles(path.resolve('../pwa_tests/fixtures/student-results-photo.webp'))
    await expect(page.getByText('Черновик сохранён на устройстве.')).toBeVisible()
    await page.reload()
    await expect(composer).toHaveValue(question)
    await expect(page.getByRole('img', { name: 'Выбранная фотография' })).toBeVisible()
    await context.setOffline(true)
    await page.getByRole('button', { name: 'Отправить', exact: true }).click()
    await expect(
      page.getByRole('alert').filter({ hasText: 'Сообщение не отправлено' }),
    ).toBeVisible()
    await context.setOffline(false)
    const sent = page.waitForResponse(
      (r) =>
        r.request().method() === 'POST' &&
        r.url().endsWith(`/${audience}/api/v1/organizer-questions`),
    )
    await page.getByRole('button', { name: 'Отправить', exact: true }).click()
    expect((await sent).status()).toBe(200)
    await expect(page).toHaveURL(new RegExp(`/${audience}/organizers/oq-\\d+`))
    const id = new URL(page.url()).pathname.split('/').at(-1)!
    const photo = page
      .getByRole('img', { name: 'Фотография в обращении', exact: true })
      .locator('img')
      .or(page.locator('img[alt="Фотография в обращении"]'))
      .first()
    await expect(photo).toBeVisible()
    await expect
      .poll(() =>
        page
          .locator('img[alt="Фотография в обращении"]')
          .first()
          .evaluate((img: HTMLImageElement) => img.naturalWidth),
      )
      .toBeGreaterThan(0)
    const admin = await secondaryContext.newPage()
    await loginThroughUi(admin, AUTH_PERSONAS.admin, '/staff/questions?state=awaiting_staff')
    await admin.getByRole('link', { name: /Вопросы организаторам/ }).click()
    await admin.getByRole('button').filter({ hasText: question }).click()
    await expect(admin).toHaveURL(`/staff/questions/organizers/${id}`)
    await admin.getByLabel('Сообщение организаторам').fill(reply)
    await admin
      .getByLabel('Прикрепить фотографии')
      .setInputFiles(path.resolve('../pwa_tests/fixtures/student-results-photo.webp'))
    await admin.getByRole('button', { name: 'Отправить', exact: true }).click()
    await expect(admin.getByText(reply, { exact: true })).toBeVisible()
    await expect(page.getByText(reply, { exact: true })).toBeVisible({ timeout: 15_000 })
    await page.goto(`/${audience}/profile`)
    const inboxLink = page.getByRole('link', { name: /Вопросы организаторам/ })
    await expect(inboxLink).toContainText(/· [1-9]/)
    await inboxLink.click()
    await page.getByRole('button').filter({ hasText: question }).click()
    await expect(page.getByText(reply, { exact: true })).toBeVisible()
    await page.goto(`/${audience}/profile/notifications`)
    const notification = page.locator(`a[href="/${audience}/organizers/${id}"]`)
    await expect(notification).toBeVisible()
    await notification.click()
    await expect(page.getByText(reply, { exact: true })).toBeVisible()
    await admin.screenshot({
      path: info.outputPath(`organizers-${audience}-staff.png`),
      animations: 'disabled',
    })
    for (const width of [320, 390]) {
      await page.setViewportSize({ width, height: 844 })
      await expect
        .poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
        .toBe(true)
      await page.screenshot({
        path: info.outputPath(`organizers-${audience}-${width}.png`),
        animations: 'disabled',
      })
    }
    await page.getByRole('button', { name: 'Переключить на тёмную тему' }).click()
    await expect(page.getByRole('button', { name: 'Переключить на светлую тему' })).toBeVisible()
    await page.screenshot({
      path: info.outputPath(`organizers-${audience}-dark.png`),
      animations: 'disabled',
    })
    await page.setViewportSize({ width: 1440, height: 1000 })
    await page.getByRole('button', { name: 'Переключить на светлую тему' }).click()
    await page.screenshot({
      path: info.outputPath(`organizers-${audience}-desktop.png`),
      animations: 'disabled',
    })
    await page.evaluate(() => {
      document.documentElement.style.zoom = '2'
    })
    await expect(composer).toBeEnabled()
    await composer.focus()
    await composer.fill('Спасибо!')
    await composer.press('Control+Enter')
    await expect(page.getByText('Спасибо!', { exact: true })).toBeVisible()
    await page.screenshot({
      path: info.outputPath(`organizers-${audience}-200.png`),
      animations: 'disabled',
    })
    await expect(admin.getByText('Спасибо!', { exact: true })).toBeVisible({ timeout: 15_000 })
  })
}

test('Organizers: teacher cannot see queue or photos', async ({ page }) => {
  await loginThroughUi(
    page,
    AUTH_PERSONAS.teacher,
    '/staff/questions/organizers?state=awaiting_staff',
  )
  await expect(page.getByRole('alert')).toContainText('только администраторам')
  for (const suffix of ['', '/photos/oqp-1']) {
    const response = await page.request.get(`/staff/api/v1/organizer-questions${suffix}`)
    expect(response.status()).toBe(403)
  }
})
