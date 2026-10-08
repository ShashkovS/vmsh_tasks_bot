import { AUTH_PERSONAS, loginThroughUi } from './auth-personas'
import { expect, test } from './fixtures'

// docs/live-marking.md: delayed transport must not look committed; real WS fan-out/resync.
test('Classroom marks wait for receipts and follow other teachers through reconnect', async ({
  page,
  context,
  secondaryContext,
}, info) => {
  test.setTimeout(120000)
  const lesson = { chromium: 931, webkit: 932, firefox: 933 }[info.project.name]!
  const fixture = 19000 + lesson
  const path = `/staff/in-person?event=ipe-${fixture}&room=room-${fixture}`
  await loginThroughUi(
    page,
    {
      ...AUTH_PERSONAS.teacher,
      username: `live-${info.project.name}`,
      accountPublicId: `a-${fixture}`,
    },
    path,
  )
  await page.getByRole('button', { name: 'Добавить в группу школьника' }).click()
  const student = `Тестов ${info.project.name} Ученик`
  await page.getByRole('searchbox', { name: 'Поиск школьника' }).fill(`Тестов ${info.project.name}`)
  await page.getByRole('button', { name: new RegExp(student) }).click()
  await page.getByRole('button', { name: `Перенести в 101 live-${info.project.name}` }).click()
  const colleague = await secondaryContext.newPage()
  let invalidations = 0
  colleague.on('websocket', (socket) => {
    if (socket.url().includes('/staff/ws'))
      socket.on('framereceived', (frame) => {
        if (String(frame.payload).includes(`live-cells/gl-${lesson}`)) invalidations++
      })
  })
  await loginThroughUi(colleague, AUTH_PERSONAS.teacher, path)
  const label = new RegExp(`^${student}, задача ${lesson}н\\.1:`)
  const mine = page.getByRole('button', { name: label })
  const theirs = colleague.getByRole('button', { name: label })
  await expect(mine).toBeVisible()
  await expect(theirs).toBeVisible()
  let release!: () => void
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })
  await page.route('**/live-marking/operations', async (route) => {
    await gate
    await route.continue()
  })
  try {
    await mine.click()
    await expect(mine).toContainText('→ +')
    await expect(mine).toHaveAccessibleName(/Ожидает отправки/)
    await expect(mine).toHaveAccessibleName(/Сохранение не подтверждено/, { timeout: 7000 })
    await expect(mine).toHaveClass(/bg-destructive/)
    await page.screenshot({ path: info.outputPath('unconfirmed-desktop.png') })
    await page.getByRole('button', { name: 'Переключить на тёмную тему' }).click()
    await page.setViewportSize({ width: 390, height: 844 })
    await page.screenshot({ path: info.outputPath('unconfirmed-mobile-dark.png') })
  } finally {
    release()
  }
  await expect(mine).toHaveAccessibleName(/\+, моя оценка, Сохранено/)
  await expect(theirs).toHaveAccessibleName(/\+, Сохранено/)
  expect(invalidations).toBeGreaterThan(0)
  await page.unroute('**/live-marking/operations')
  await context.setOffline(true)
  await theirs.click()
  await theirs.click()
  await expect(theirs).toHaveAccessibleName(/−, моя оценка, Сохранено/)
  await context.setOffline(false)
  await expect(mine).toHaveAccessibleName(/−, Сохранено/, { timeout: 20000 })
  await page.reload()
  await expect(page.getByRole('button', { name: label })).toHaveAccessibleName(/−, Сохранено/)
})
