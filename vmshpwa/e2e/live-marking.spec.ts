import { liveDirectorySchema } from '../packages/contracts/src/live-marking'
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

test('Live student search ignores patronymics and can match only surnames', async ({
  page,
}, info) => {
  const project = info.project.name
  const fixture = 19000 + numbers[project]!
  const classroomStudentName = `Тестов ${project} Ученик`
  const patronymicOnlyStudentName = `БезАккаунта ${project} Новый`

  await loginThroughUi(page, persona(project), '/staff/oral?course=c-1')
  let search = page.getByRole('searchbox', { name: 'Поиск школьника' })
  let surnameOnly = page.getByRole('switch', { name: 'Искать только по фамилии' })
  let classroomStudent = page.getByRole('button', {
    name: new RegExp(classroomStudentName),
  })
  await search.fill(`Тестов ${project}`)
  await expect(classroomStudent).toBeVisible()
  await expect(page.getByText(patronymicOnlyStudentName, { exact: true })).toHaveCount(0)
  await surnameOnly.click()
  await expect(surnameOnly).toHaveAttribute('aria-checked', 'true')
  await search.fill('Ученик')
  await expect(classroomStudent).toHaveCount(0)
  await search.fill(`Тестов ${project}`)
  await expect(classroomStudent).toBeVisible()

  await page.goto(`/staff/in-person?event=ipe-${fixture}&room=room-${fixture}`)
  await page.getByRole('button', { name: 'Добавить в группу школьника' }).click()
  search = page.getByRole('searchbox', { name: 'Поиск школьника' })
  surnameOnly = page.getByRole('switch', { name: 'Искать только по фамилии' })
  classroomStudent = page.getByRole('button', { name: new RegExp(classroomStudentName) })
  await expect(surnameOnly).toHaveAttribute('aria-checked', 'false')
  await search.fill(`Тестов ${project}`)
  await expect(classroomStudent).toBeVisible()
  await expect(page.getByText(patronymicOnlyStudentName, { exact: true })).toHaveCount(0)
  await surnameOnly.click()
  await expect(surnameOnly).toHaveAttribute('aria-checked', 'true')
  await search.fill('Ученик')
  await expect(classroomStudent).toHaveCount(0)
  await search.fill(`Тестов ${project}`)
  await expect(classroomStudent).toBeVisible()
})

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
  const cell = page.getByRole('button', { name: new RegExp(`^Задача ${lesson}н\\.1:`) })
  await expect(cell).toBeVisible()
  let writes = 0
  page.on('request', (request) => {
    if (request.method() === 'POST' && request.url().endsWith('/live-marking/operations')) writes++
  })
  const marks = page.getByRole('button', { name: /^Задача / })
  await expect(marks).toHaveCount(24)
  const firstBox = await marks.first().boundingBox()
  const lastBox = await marks.last().boundingBox()
  // docs/task-titles.md: six compact rows now include visible, wrapped names.
  expect(lastBox!.y - firstBox!.y).toBeLessThan(560)
  // Level controls take one extra row; all tasks remain reachable in the grid.
  await marks.last().scrollIntoViewIfNeeded()
  await expect(marks.last()).toBeInViewport({ ratio: 1 })
  await marks.first().scrollIntoViewIfNeeded()
  await expect(page.getByText('Расскажите решение', { exact: true }).first()).toBeVisible()
  await page.screenshot({
    path: info.outputPath('live-zoom-titles-mobile.png'),
    animations: 'disabled',
  })
  const conditionButton = page.getByRole('button', {
    name: `Показать условие задачи ${lesson}н.1`,
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
  await expect(cell).toHaveAccessibleName(/не сдавал/)
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
  page.once('dialog', (dialog) => dialog.accept())
  await page
    .getByRole('button', { name: /Снять мои оценки в этом приёме/ })
    .first()
    .click()
  await expect(cell).toContainText('→ ∅')
  await expect(cell).toHaveAccessibleName(/не сдавал, Сохранено/)
  await page.getByRole('button', { name: 'Отменить последнее действие' }).click()
  await expect(cell).toHaveAccessibleName(/\+, моя оценка, Сохранено/)
  await page.keyboard.press('Control+z')
  await expect(cell).toHaveAccessibleName(/не сдавал, Сохранено/)
  await cell.click()
  await expect(cell).toHaveAccessibleName(/\+, моя оценка, Сохранено/)
  await page.getByRole('button', { name: 'Отменить последнее действие' }).click()
  await expect(cell).toHaveAccessibleName(/не сдавал, Сохранено/)
  await context.setOffline(true)
  await cell.click()
  await expect(page.getByRole('status').filter({ hasText: 'не отправлено' })).toBeVisible()
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
  // Clear, undo clear, undo the original plus, then another plus add four writes.
  expect(writes).toBe(10)
  await page.keyboard.press('Escape')
  const resumed = await context.newPage()
  await resumed.goto(page.url())
  const resumedCell = resumed.getByRole('button', { name: new RegExp(`^Задача ${lesson}н\\.1:`) })
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
  const mine = page.getByRole('button', {
    name: new RegExp(`^${student}, задача ${numbers[project]}н\\.1:`),
  })
  const theirs = colleague.getByRole('button', {
    name: new RegExp(`^${student}, задача ${numbers[project]}н\\.1:`),
  })
  await expect(theirs).toBeVisible()
  await mine.click()
  await expect(mine).toHaveAccessibleName(/\+, моя оценка, Сохранено/)
  await expect(theirs).toHaveAccessibleName(/\+, Сохранено/)
  await theirs.click()
  await theirs.click()
  await expect(theirs).toHaveAccessibleName(/−, моя оценка, Сохранено/)
  await expect(mine).toHaveAccessibleName(/−, Сохранено/)
  await page.getByRole('button', { name: 'Отменить последнее действие' }).click()
  await expect(page.getByRole('alert').filter({ hasText: 'Ячейка уже изменена.' })).toBeVisible()
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

// docs/live-marking.md: marks keep their original worksheet during navigation.
test('Live Zoom: two levels share one session without changing enrollment', async ({
  page,
}, info) => {
  const number = numbers[info.project.name]!
  await loginThroughUi(page, persona(info.project.name), '/staff/oral?course=c-1')
  await page.getByRole('searchbox', { name: 'Поиск школьника' }).fill('Тестовый-Онлайн Алексей')
  await page.getByRole('button', { name: /Тестовый-Онлайн Алексей/ }).click()
  await page.getByRole('combobox', { name: 'Занятие', exact: true }).selectOption(`gl-${number}`)
  const originalUrl = page.url()
  const session = new URL(originalUrl).searchParams.get('session')
  const levels = page.getByRole('group', { name: 'Уровень задач', exact: true })
  const own = levels.getByRole('button', { pressed: true })
  const ownName = await own.innerText()
  const other = levels.getByRole('button', { pressed: false }).filter({ hasText: 'Продолжающие' })
  await expect(other).toBeEnabled()
  const first = page.getByRole('button', { name: new RegExp(`^Задача ${number}н\\.2:`) })
  const second = page.getByRole('button', { name: new RegExp(`^Задача ${number}н\\.3:`) })
  await expect(first).toHaveAccessibleName(/не сдавал/)
  let release!: () => void
  const held = new Promise<void>((resolve) => {
    release = resolve
  })
  await page.route('**/live-marking/operations', async (route) => {
    await held
    await route.continue()
  })
  await first.click()
  await second.click()
  await other.click()
  await expect(page.getByRole('combobox', { name: 'Занятие', exact: true })).toHaveValue(
    `gl-${number + 10}`,
  )
  await expect(page.getByRole('status').filter({ hasText: 'не отправлено' })).toBeVisible()
  const third = page.getByRole('button', { name: new RegExp(`^Задача ${number}п\\.1:`) })
  await third.click()
  release()
  await expect(third).toHaveAccessibleName(/\+, моя оценка, Сохранено/)
  await page.unroute('**/live-marking/operations')
  expect(new URL(page.url()).searchParams.get('session')).toBe(session)
  await page
    .getByRole('group', { name: 'Тип задач', exact: true })
    .getByRole('button', { name: 'Все', exact: true })
    .click()
  await page.reload()
  await expect(third).toHaveAccessibleName(/\+, моя оценка, Сохранено/)
  await expect(
    page
      .getByRole('group', { name: 'Тип задач', exact: true })
      .getByRole('button', { name: 'Все', exact: true }),
  ).toHaveAttribute('aria-pressed', 'true')
  await levels.getByRole('button', { name: ownName, exact: true }).click()
  await expect(first).toHaveAccessibleName(/\+, моя оценка, Сохранено/)
  await expect(second).toHaveAccessibleName(/\+, моя оценка, Сохранено/)
  await page.goBack()
  await expect(third).toHaveAccessibleName(/\+, моя оценка, Сохранено/)
  await page.getByRole('button', { name: /За сессию · 1/ }).click()
  const visit = page
    .getByRole('dialog')
    .getByRole('button', { name: new RegExp(`Занятие ${number} · ${ownName}`) })
  await visit.click()
  await expect(first).toHaveAccessibleName(/\+, моя оценка, Сохранено/)
  const directory = await page.request.get('/staff/api/v1/live-marking/directory?courseId=c-1')
  const pupil = liveDirectorySchema
    .parse(await directory.json())
    .students.find(
      (item: { displayName: string }) => item.displayName === 'Тестовый-Онлайн Алексей',
    )
  expect(pupil?.groupName).toBe(ownName)
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 900 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: info.outputPath(`oral-levels-${width}.png`), fullPage: true })
  }
  await page.getByRole('button', { name: 'Переключить на тёмную тему' }).click()
  await page.screenshot({ path: info.outputPath('oral-levels-dark.png'), fullPage: true })
  // Keyboard navigation and an offline change remain scoped to the second level.
  await other.focus()
  await page.keyboard.press('Enter')
  await expect(third).toHaveAccessibleName(/\+, моя оценка, Сохранено/)
  await page.context().setOffline(true)
  await third.click()
  await third.click()
  await levels.getByRole('button', { name: ownName, exact: true }).click()
  await expect(page.getByRole('status').filter({ hasText: 'не отправлено' })).toBeVisible()
  await page.context().setOffline(false)
  await other.click()
  await expect(third).toHaveAccessibleName(/−, моя оценка, Сохранено/)
  await page.getByRole('button', { name: 'Отменить последнее действие' }).click()
  await expect(third).toHaveAccessibleName(/\+, моя оценка, Сохранено/)
})
