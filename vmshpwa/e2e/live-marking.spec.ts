import { AUTH_PERSONAS, loginThroughUi, type AuthPersona } from './auth-personas'
import { expect, test } from './fixtures'

// Owner acceptance: vmshpwa/docs/live-marking.md. Real API + websocket + IndexedDB.
const numbers: Record<string, number> = { chromium: 931, webkit: 932, firefox: 933 }
function persona(project: string): AuthPersona {
  return {
    ...AUTH_PERSONAS.teacher,
    username: `live-${project}`,
    accountPublicId: `a-${19000 + numbers[project]!}`,
  }
}
test.setTimeout(120_000)

test('Live Zoom: fast cycle, delayed save, undo, offline recovery and mobile reactions', async ({
  page,
  context,
}, info) => {
  const lesson = numbers[info.project.name]!
  await page.setViewportSize({ width: 390, height: 844 })
  await loginThroughUi(page, persona(info.project.name), '/staff/oral?course=c-1')
  await page.getByRole('searchbox', { name: 'Поиск школьника' }).fill('Тестовый-Онлайн Алексей')
  await page.getByRole('button', { name: /Тестовый-Онлайн Алексей/ }).click()
  await page.getByRole('combobox', { name: 'Занятие', exact: true }).selectOption(`gl-${lesson}`)
  const cell = page.getByRole('button', { name: /^Задача 1:/ })
  await expect(cell).toBeVisible()
  let writes = 0
  page.on('request', (request) => {
    if (request.method() === 'POST' && request.url().endsWith('/live-marking/operations')) writes++
  })
  const marks = page.getByRole('button', { name: /^Задача / })
  await expect(marks).toHaveCount(24)
  const firstBox = await marks.first().boundingBox()
  const lastBox = await marks.last().boundingBox()
  expect(lastBox!.y - firstBox!.y).toBeLessThan(380)
  expect(lastBox!.y + lastBox!.height).toBeLessThan(740)
  const conditionButton = page.getByRole('button', {
    name: 'Показать условие задачи 1',
    exact: true,
  })
  await conditionButton.click()
  await expect(page.getByRole('dialog')).toContainText('Расскажите решение преподавателю')
  await page.screenshot({
    path: info.outputPath('live-condition-mobile.png'),
    fullPage: true,
    animations: 'disabled',
  })
  await page.getByRole('button', { name: 'К оценкам' }).click()
  await expect(conditionButton).toBeFocused()
  await expect(cell).toHaveAccessibleName(/пусто/)
  expect(writes).toBe(0)
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.screenshot({
    path: info.outputPath('live-zoom-desktop.png'),
    fullPage: true,
    animations: 'disabled',
  })
  await page.setViewportSize({ width: 390, height: 844 })
  await cell.click()
  await cell.click()
  await cell.click()
  await page.waitForTimeout(2200) // Proves a complete cycle never crosses the debounce boundary.
  expect(writes).toBe(0)
  await cell.click()
  await expect(cell).toHaveAccessibleName(/\+, моя оценка, Сохранено/)
  expect(writes).toBe(1)
  await page.reload()
  await expect(cell).toHaveAccessibleName(/\+, моя оценка, Сохранено/)
  await page.getByRole('button', { name: 'Отменить последнее действие' }).click()
  await expect(cell).toHaveAccessibleName(/пусто, Сохранено/)
  await context.setOffline(true)
  await cell.click()
  await expect(page.getByRole('status')).toContainText('не отправлено')
  await context.setOffline(false)
  await expect(cell).toHaveAccessibleName(/\+, моя оценка, Сохранено/)
  await page.getByRole('button', { name: '👍 Круто', exact: true }).click()
  await expect(page.getByRole('button', { name: '👍 Круто', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await page.getByRole('button', { name: '🤖 ИИ', exact: true }).click()
  await expect(page.getByRole('button', { name: '🤖 ИИ', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await page.getByRole('button', { name: 'Похвалить ученика' }).click()
  await expect(page.getByRole('button', { name: 'Похвала отправлена' })).toBeVisible()
  await page.screenshot({
    path: info.outputPath('live-zoom-mobile.png'),
    fullPage: true,
    animations: 'disabled',
  })
  await page.getByRole('button', { name: 'Переключить на тёмную тему' }).click()
  await page.screenshot({
    path: info.outputPath('live-zoom-mobile-dark.png'),
    fullPage: true,
    animations: 'disabled',
  })
  await page.getByRole('button', { name: 'Переключить на светлую тему' }).click()
  await page.setViewportSize({ width: 320, height: 640 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  )
  expect((await cell.boundingBox())!.width).toBeGreaterThanOrEqual(44)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.getByRole('button', { name: /За сессию/ }).click()
  await expect(page.getByRole('dialog')).toContainText('Тестовый-Онлайн Алексей')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  )
  expect(writes).toBe(6)
  await page.keyboard.press('Escape')
  const resumed = await context.newPage()
  await resumed.goto(page.url())
  const resumedCell = resumed.getByRole('button', { name: /^Задача 1:/ })
  await expect(resumedCell).toHaveAccessibleName(/\+, моя оценка, Сохранено/)
  await page.getByRole('button', { name: /За сессию/ }).click()
  await page.getByRole('button', { name: 'Завершить сессию' }).click()
  await expect(resumedCell).toBeDisabled()
  await resumed.close()
})

test('Live classroom: teacher transfer, attendance and another teacher sees the saved mark', async ({
  page,
  secondaryContext,
}, info) => {
  const project = info.project.name
  const fixture = 19000 + numbers[project]!
  const path = `/staff/in-person?event=ipe-${fixture}&room=room-${fixture}`
  await loginThroughUi(page, persona(project), path)
  await page.getByRole('button', { name: 'Добавить в группу школьника' }).click()
  await page.getByRole('searchbox', { name: 'Поиск школьника' }).fill(`Тестов ${project}`)
  await page.getByRole('button', { name: new RegExp(`Тестов ${project} Ученик`) }).click()
  await page.getByRole('button', { name: `Перенести в 101 live-${project}` }).click()
  const student = `Тестов ${project} Ученик`
  await expect(page.getByRole('button', { name: `${student}: Пришёл` })).toBeVisible()
  await page.getByRole('button', { name: student, exact: true }).click()
  await expect(
    page.getByRole('button', { name: new RegExp(`^${student}`) }).filter({ hasText: '7 кл.' }),
  ).toHaveAttribute('aria-expanded', 'true')
  const colleague = await secondaryContext.newPage()
  await loginThroughUi(colleague, AUTH_PERSONAS.teacher, path)
  const mine = page.getByRole('button', { name: new RegExp(`^${student}, задача 1:`) })
  const theirs = colleague.getByRole('button', { name: new RegExp(`^${student}, задача 1:`) })
  await expect(theirs).toBeVisible()
  await mine.click()
  await expect(mine).toHaveAccessibleName(/\+, моя оценка, Сохранено/)
  await expect(theirs).toHaveAccessibleName(/\+, Сохранено/)
  await theirs.click()
  await theirs.click()
  await expect(theirs).toHaveAccessibleName(/−, моя оценка, Сохранено/)
  await expect(mine).toHaveAccessibleName(/−, Сохранено/)
  await page.getByRole('button', { name: 'Отменить последнее действие' }).click()
  await expect(page.getByRole('alert')).toContainText('Данные уже изменились')
  await page.getByRole('button', { name: `${student}: Пришёл` }).click()
  await expect(page.getByRole('button', { name: `${student}: Отсутствует` })).toBeVisible()
  await page.getByRole('button', { name: 'Все', exact: true }).click()
  await expect(page.getByRole('button', { name: `${student}: Отсутствует` })).toHaveCount(0)
  await page.getByRole('button', { name: 'Пришли', exact: true }).click()
  await page.setViewportSize({ width: 390, height: 844 })
  const settings = page.getByRole('button', { name: 'Настройки занятия' })
  const settingsBox = await settings.boundingBox()
  const filterBox = await page.getByRole('button', { name: 'Все', exact: true }).boundingBox()
  expect(Math.abs(settingsBox!.y - filterBox!.y)).toBeLessThan(5)
  const nameBox = await page.getByRole('rowheader').filter({ hasText: student }).boundingBox()
  expect(nameBox!.width).toBeLessThanOrEqual(114)
  await settings.click()
  await expect(
    page.getByRole('dialog').getByRole('combobox', { name: 'Аудитория', exact: true }),
  ).toBeVisible()
  await page.getByRole('button', { name: 'Готово', exact: true }).click()
  await expect(settings).toBeFocused()
  await page.screenshot({
    path: info.outputPath('live-classroom-mobile.png'),
    fullPage: true,
    animations: 'disabled',
  })
})
