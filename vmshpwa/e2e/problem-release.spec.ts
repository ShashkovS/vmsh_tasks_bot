import { AUTH_PERSONAS, loginThroughUi } from './auth-personas'
import { expect, test } from './fixtures'

// docs/problem-release.md: three live readers, real aiohttp, no page reload.
test('teacher releases fifteen tasks progressively to Student and Family', async ({
  page,
  secondaryContext,
}, testInfo) => {
  test.setTimeout(120_000)
  const lesson = { chromium: 15101, webkit: 15102, firefox: 15103 }[testInfo.project.name]!
  const student = await secondaryContext.newPage()
  const family = await secondaryContext.newPage()
  await loginThroughUi(student, AUTH_PERSONAS.student, `/student/tasks/math-5-7/н/${lesson}`)
  await loginThroughUi(family, AUTH_PERSONAS.family, `/family/tasks/math-5-7/н/${lesson}`)
  await loginThroughUi(page, AUTH_PERSONAS.admin, `/staff/lessons/gl-${lesson}`)
  const workflow = page.getByTestId('content-workflow-condition')
  const load = workflow.getByRole('button', { name: 'Показать PWA и Telegram' })
  await load.click()
  const controls = page.getByRole('region', { name: 'Позадачная публикация' })
  await expect(controls).toBeVisible()
  await expect(workflow.getByRole('switch')).toHaveCount(15)
  await expect(workflow.getByRole('alert')).toHaveCount(0)
  const studentTasks = student.getByRole('heading', { name: /^Задача / })
  const familyTasks = family.getByRole('heading', { name: /^Задача / })
  await expect(studentTasks).toHaveCount(15)
  await expect(familyTasks).toHaveCount(15)
  const navigations: string[] = []
  student.on('framenavigated', (frame) => {
    if (frame === student.mainFrame()) navigations.push(frame.url())
  })
  family.on('framenavigated', (frame) => {
    if (frame === family.mainFrame()) navigations.push(frame.url())
  })
  await controls.getByRole('button', { name: 'Закрыть все' }).click()
  await expect(student.getByText('Задачи скоро откроются.', { exact: true })).toBeVisible()
  await expect(family.getByText('Задачи скоро откроются.', { exact: true })).toBeVisible()
  await expect(studentTasks).toHaveCount(0)
  await expect(familyTasks).toHaveCount(0)
  await student.screenshot({ path: testInfo.outputPath('student-waiting.png') })
  await family.screenshot({ path: testInfo.outputPath('family-waiting.png') })
  for (const index of [0, 1]) {
    await workflow.getByRole('switch').nth(index).click()
    await expect(workflow.getByRole('switch').nth(index)).toBeEnabled()
  }
  await expect(studentTasks).toHaveCount(2)
  await expect(familyTasks).toHaveCount(2)
  await controls.scrollIntoViewIfNeeded()
  await page.screenshot({ path: testInfo.outputPath('staff-release-preview.png') })
  await page.screenshot({ path: testInfo.outputPath('staff-two-open.png'), fullPage: true })
  await student.screenshot({ path: testInfo.outputPath('student-two-open.png'), fullPage: true })
  await family.screenshot({ path: testInfo.outputPath('family-two-open.png'), fullPage: true })
  for (const [name, reader] of [
    ['staff', page],
    ['student', student],
    ['family', family],
  ] as const) {
    await reader.getByRole('button', { name: 'Переключить на тёмную тему' }).click()
    await reader.screenshot({
      path: testInfo.outputPath(`${name}-dark-two-open.png`),
      fullPage: true,
    })
    await reader.setViewportSize({ width: 390, height: 844 })
    await reader.screenshot({
      path: testInfo.outputPath(`${name}-mobile-two-open.png`),
      fullPage: true,
    })
    await reader.setViewportSize({ width: 1280, height: 720 })
    await reader.getByRole('button', { name: 'Переключить на светлую тему' }).click()
  }
  for (const index of [2, 3, 4]) {
    await workflow.getByRole('switch').nth(index).click()
    await expect(workflow.getByRole('switch').nth(index)).toBeEnabled()
  }
  await expect(studentTasks).toHaveCount(5)
  await expect(familyTasks).toHaveCount(5)
  await secondaryContext.setOffline(true)
  // WebKit/Firefox do not consistently emit browser availability events for
  // setOffline. Keep real network loss and deliver the same events as a device.
  for (const reader of [student, family])
    await reader.evaluate(() => {
      Object.defineProperty(navigator, 'onLine', { configurable: true, get: () => false })
      dispatchEvent(new Event('offline'))
    })
  await controls.getByRole('button', { name: 'Открыть все' }).click()
  await expect(controls.getByRole('status')).toHaveText('Открыто 15 из 15')
  await expect(studentTasks).toHaveCount(5)
  await expect(familyTasks).toHaveCount(5)
  await secondaryContext.setOffline(false)
  for (const reader of [student, family])
    await reader.evaluate(() => {
      Object.defineProperty(navigator, 'onLine', { configurable: true, get: () => true })
      dispatchEvent(new Event('online'))
    })
  await student.bringToFront()
  await expect(studentTasks).toHaveCount(15, { timeout: 30_000 })
  await family.bringToFront()
  await expect(familyTasks).toHaveCount(15, { timeout: 30_000 })
  // Retraction also reaches already open readers.
  await workflow.getByRole('switch').nth(0).click()
  await expect(studentTasks).toHaveCount(14)
  await expect(familyTasks).toHaveCount(14)
  await controls.getByRole('button', { name: 'Открыть все' }).click()
  await expect(studentTasks).toHaveCount(15)
  await expect(familyTasks).toHaveCount(15)
  expect(navigations).toEqual([])
})
