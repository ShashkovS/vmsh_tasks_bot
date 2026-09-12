import { AUTH_PERSONAS, loginThroughUi } from './auth-personas'
import { expect, test } from './fixtures'

// Route latency injection must also intercept WebKit requests, which otherwise run through SW.
test.use({ serviceWorkers: 'block' })

// docs/task-interaction-polish.md: real backend, delay only its request delivery.
test('task references, worksheet return, narrow composer and delayed sending', async ({
  page,
}, testInfo) => {
  test.setTimeout(90_000)
  const ids: Record<string, number> = { chromium: 32101, webkit: 32102, firefox: 32103 }
  const lesson = ids[testInfo.project.name]!
  const path = `/student/tasks/math-5-7/${encodeURIComponent('н')}/${lesson}`
  await loginThroughUi(page, AUTH_PERSONAS.student, path)
  await expect(
    page.getByRole('heading', { name: new RegExp(`Задача ${lesson}н\\.1\\.`) }),
  ).toBeVisible()
  await page.goto(`/student/tasks/math-5-7/${encodeURIComponent('н')}/${lesson + 1000}`)
  await expect(page.getByRole('heading', { name: /Устная E2E/ })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Мой ответ', exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Показать все ответы', exact: true })).toHaveCount(
    0,
  )
  await page.goto(path)
  const open = page.getByRole('button', { name: /^Открыть задачу/ }).first()
  await page.evaluate(() => window.scrollTo(0, 100))
  const top = (await open.boundingBox())!.y
  await open.click()
  await expect(page.getByRole('textbox', { name: 'Ваше решение' })).toBeVisible()
  await page.getByRole('button', { name: 'К листку' }).click()
  await expect(page).toHaveURL(new RegExp(`${lesson}$`))
  await expect.poll(async () => Math.abs((await open.boundingBox())!.y - top)).toBeLessThan(3)
  await open.click()
  const input = page.getByRole('textbox', { name: 'Ваше решение' })
  const submission = page.getByRole('region', { name: 'Сдать решение' })
  for (const width of [320, 390]) {
    await page.setViewportSize({ width, height: 800 })
    await input.fill('Моё решение: разобьём фигуру на два треугольника.')
    const box = (await input.boundingBox())!
    const send = (await submission
      .getByRole('button', { name: 'Отправить', exact: true })
      .boundingBox())!
    expect(send.y).toBeGreaterThanOrEqual(box.y + box.height)
    expect(box.width).toBeGreaterThan(width - 95)
    await page.screenshot({ path: testInfo.outputPath(`composer-${width}.png`), fullPage: true })
  }
  let release!: () => void
  const gate = new Promise<void>((resolve) => {
    release = resolve
  })
  await page.route('**/student/api/v1/**/submit', async (route) => {
    await gate
    const response = await route.fetch()
    expect(response.ok()).toBe(true)
    await route.fulfill({ response })
  })
  await submission.getByRole('button', { name: 'Отправить', exact: true }).click()
  await expect(page.getByText('Отправляем…', { exact: true }).last()).toBeVisible()
  await expect(page.getByText('Отправка ещё не подтверждена.', { exact: false })).toHaveCount(0)
  await expect(page.getByText('Отправка занимает больше времени', { exact: false })).toBeVisible({
    timeout: 5_000,
  })
  await page.screenshot({ path: testInfo.outputPath('delayed.png'), fullPage: true })
  release()
  await expect(page.getByText('Отправка занимает больше времени', { exact: false })).toHaveCount(0)
  await page.unrouteAll({ behavior: 'wait' })
  await page.reload()
  await expect(input).toHaveValue('')
  await expect(
    page.getByText('Моё решение: разобьём фигуру на два треугольника.', { exact: false }),
  ).toBeVisible()
  await page.goto('/student/tasks')
  await expect(page.locator('[data-print-lesson]')).toHaveCount(5)
  await page.getByRole('button', { name: 'Показать более ранние занятия' }).click()
  await expect(page.locator('[data-print-lesson]')).toHaveCount(10)
  const last = page.getByRole('button', { name: /^Открыть задачу/ }).last()
  await last.scrollIntoViewIfNeeded()
  const lastTop = (await last.boundingBox())!.y
  await last.click()
  await page.getByRole('button', { name: 'К листку' }).click()
  await expect(page.locator('[data-print-lesson]')).toHaveCount(10)
  await expect.poll(async () => Math.abs((await last.boundingBox())!.y - lastTop)).toBeLessThan(3)
})
