import { test, expect } from './fixtures'
import { AUTH_PERSONAS, loginThroughUi } from './auth-personas'

test('Weekly oral draft: choose days, persist, save, clone and edit', async ({ page }, info) => {
  test.setTimeout(90000)
  const lesson = { chromium: 921, webkit: 922, firefox: 923 }[info.project.name]!
  await loginThroughUi(
    page,
    AUTH_PERSONAS.admin,
    `/staff/oral?groupLesson=gl-${lesson}&tab=windows`,
  )
  await expect(page.getByRole('heading', { name: 'Черновик окон' })).toBeVisible()
  await page.getByLabel('Открывается', { exact: true }).fill('2030-10-07T18:00')
  await page.getByLabel('Закрывается', { exact: true }).fill('2030-10-07T20:00')
  await page.getByLabel('HTTPS-ссылка', { exact: true }).fill('https://zoom.example.test/weekly')
  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('button', { name: 'Пн / вт / ср', exact: true }).click()
  await page.getByRole('checkbox', { name: 'Окно 2', exact: true }).uncheck()
  await page.reload()
  await expect(page.getByRole('checkbox', { name: 'Окно 2', exact: true })).not.toBeChecked()
  const response = page.waitForResponse(
    (r) => r.url().endsWith('/oral-windows/batch') && r.request().method() === 'POST',
  )
  await page.getByRole('button', { name: 'Создать выбранные окна', exact: true }).click()
  expect((await response).status()).toBe(201)
  await expect(page.getByRole('status')).toContainText('Окна созданы')
  const scheduled = page.getByRole('region', { name: 'Настроенные окна' })
  await expect(scheduled.getByRole('button', { name: 'Клонировать', exact: true })).toHaveCount(3)
  page.once('dialog', (dialog) => dialog.accept())
  await scheduled.getByRole('button', { name: 'Клонировать', exact: true }).last().click()
  await expect(page.getByLabel('HTTPS-ссылка', { exact: true })).toHaveValue(
    'https://zoom.example.test/weekly',
  )
  await expect(page.getByLabel('Открывается', { exact: true })).toHaveValue('2030-10-10T18:00')
  await expect(scheduled.getByRole('button', { name: 'Клонировать', exact: true })).toHaveCount(3)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.screenshot({ path: info.outputPath('weekly-draft-mobile.png'), fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await scheduled.getByRole('button', { name: 'Изменить', exact: true }).last().click()
  await page.getByLabel('Подпись кнопки', { exact: true }).fill('Войти на приём')
  const edited = page.waitForResponse(
    (r) => /\/oral-windows\/ow-/.test(r.url()) && r.request().method() === 'PUT',
  )
  await page.getByRole('button', { name: 'Сохранить', exact: true }).click()
  expect((await edited).status()).toBe(200)
})
