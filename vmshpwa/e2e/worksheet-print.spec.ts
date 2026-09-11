import { AUTH_PERSONAS, loginThroughUi } from './auth-personas'
import { expect, test } from './fixtures'

// docs/worksheet-print.md: real publications, native print media, no state mutations.
test('worksheets print only mounted conditions and expanded learning materials', async ({
  page,
}, testInfo) => {
  test.setTimeout(90_000)
  const ids: Record<string, number> = { chromium: 32101, webkit: 32102, firefox: 32103 }
  const id = ids[testInfo.project.name]!
  const lessonPath = `/student/tasks/math-5-7/${encodeURIComponent('н')}/${id}`
  await loginThroughUi(page, AUTH_PERSONAS.student, lessonPath)
  const sheet = page.locator('[data-print-lesson]')
  await expect(sheet).toHaveCount(1)
  await expect(page.getByRole('heading', { name: /Длинная задача с пунктами/ })).toBeVisible()
  const images = sheet.getByRole('img')
  await expect(images).toHaveCount(2)
  for (const img of await images.all()) {
    await expect(img).toHaveAttribute('loading', 'eager')
    await expect
      .poll(() => img.evaluate((el: HTMLImageElement) => el.complete && el.naturalWidth > 0))
      .toBe(true)
  }
  const beforeRequests: string[] = []
  page.on('request', (request) => {
    if (request.url().includes('/reveal/') || /\/content\?|\/lessons(?:\?|$)/.test(request.url()))
      beforeRequests.push(request.url())
  })
  await page.emulateMedia({ media: 'print' })
  await expect(sheet.locator('button:visible')).toHaveCount(0) // roles omit CSS-hidden controls
  await expect(page.getByRole('navigation')).toHaveCount(0)
  expect(await sheet.evaluate((el) => parseFloat(getComputedStyle(el).fontSize))).toBeCloseTo(
    (11 * 96) / 72,
    3,
  )
  await expect(sheet).toHaveCSS('color', 'rgb(0, 0, 0)')
  const printWidth = await page
    .getByTestId('figure-canvas')
    .first()
    .evaluate((el) => el.getBoundingClientRect().width)
  await expect(page.getByText('Подсказка для печати:', { exact: false })).toHaveCount(0)
  expect(beforeRequests).toEqual([])
  await page.screenshot({ path: testInfo.outputPath('closed-light.png'), fullPage: true })
  if (testInfo.project.name === 'chromium') {
    const pdf = await page.pdf({
      path: testInfo.outputPath('lesson-closed.pdf'),
      preferCSSPageSize: true,
    })
    // Chromium emits page dictionaries outside compressed streams. The fixed
    // lesson is two pages; inline KaTeX fragmentation used to produce four.
    expect(pdf.toString('latin1').match(/\/Type\s*\/Page\b/g)).toHaveLength(2)
  }
  await page.emulateMedia({ media: 'screen' })

  await page.getByRole('button', { name: 'Ответить', exact: true }).click()
  const draft = page.getByRole('textbox', { name: 'Ваше решение', exact: true })
  await draft.fill('Отправленная работа не должна печататься')
  const submission = page.getByRole('region', { name: 'Сдать решение', exact: true })
  await submission
    .locator('input[type="file"]')
    .first()
    .setInputFiles('../pwa_tests/fixtures/student-results-photo.webp')
  await expect(submission.getByText('готово', { exact: true })).toBeVisible()
  const submitted = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname.endsWith('/submit'),
  )
  await submission.getByRole('button', { name: 'Отправить', exact: true }).click()
  expect((await submitted).ok()).toBe(true)
  await page.reload()
  await page.getByRole('button', { name: 'Ответить', exact: true }).click()
  await expect(draft).toHaveValue('')
  await expect(
    page.getByText('Отправленная работа не должна печататься', { exact: false }),
  ).toBeVisible()
  await draft.fill('Мой непечатаемый черновик')
  await page.getByRole('button', { name: 'Задать вопрос', exact: true }).click()
  const question = page.getByRole('textbox', { name: 'Сообщение', exact: true })
  await question.fill('Вопрос, который не должен печататься')
  await page.getByRole('button', { name: 'Подсказка', exact: true }).click()
  await expect(page.getByText('Подсказка для печати: проведите высоту AH.')).toBeVisible()
  const canvas = page.getByTestId('figure-canvas').first()
  await canvas.click()
  const enlargedWidth = await canvas.evaluate((el) => el.getBoundingClientRect().width)
  beforeRequests.length = 0
  await page.emulateMedia({ media: 'print' })
  await expect(draft).toBeHidden()
  await expect(question).toBeHidden()
  await expect(page.getByText('Подсказка для печати: проведите высоту AH.')).toBeVisible()
  await expect(page.locator('.vmsh-print-material-label')).toHaveText('Подсказка')
  expect(await canvas.evaluate((el) => el.getBoundingClientRect().width)).toBe(printWidth)
  await expect(
    page.getByText('Отправленная работа не должна печататься', { exact: false }),
  ).toBeHidden()
  await expect(submission.getByRole('img')).toHaveCount(0)
  expect(beforeRequests).toEqual([])
  await page.screenshot({ path: testInfo.outputPath('hint-light.png'), fullPage: true })
  await page.emulateMedia({ media: 'screen' })
  await expect(draft).toHaveValue('Мой непечатаемый черновик')
  await expect(question).toHaveValue('Вопрос, который не должен печататься')
  expect(await canvas.evaluate((el) => el.getBoundingClientRect().width)).toBe(enlargedWidth)
  await expect(page.locator('.vmsh-print-material-label')).toBeHidden()

  await page.getByRole('button', { name: 'Решение', exact: true }).click()
  await expect(page.getByText('Решение для печати: проведите высоту AH.')).toBeVisible()
  await page.getByRole('button', { name: 'Переключить на тёмную тему' }).click()
  await page.emulateMedia({ media: 'print' })
  await expect(page.locator('.vmsh-print-material-label')).toHaveText('Решение')
  await expect(sheet).toHaveCSS('color', 'rgb(0, 0, 0)')
  await expect(draft).toBeHidden()
  await expect(question).toBeHidden()
  await page.screenshot({ path: testInfo.outputPath('solution-dark.png'), fullPage: true })
  if (testInfo.project.name === 'chromium') {
    await page.pdf({ path: testInfo.outputPath('lesson-solution.pdf'), preferCSSPageSize: true })
  }
  await page.emulateMedia({ media: 'screen' })
  await expect(draft).toHaveValue('Мой непечатаемый черновик')

  // The readable single-task URL starts with an expanded answer panel too.
  await page
    .getByRole('button', { name: /^Открыть задачу/ })
    .first()
    .click()
  await expect(page).toHaveURL(/task=/)
  await expect(page.getByRole('heading', { name: /Длинная задача с пунктами/ })).toHaveCount(0)
  await expect(page.locator('[data-print-lesson]')).toHaveCount(1)
  await expect(page.getByRole('heading', { name: /Устная E2E/ })).toBeVisible()
  await page.emulateMedia({ media: 'print' })
  await expect(page.getByRole('textbox')).toHaveCount(0)
  await expect(page.getByRole('button')).toHaveCount(1) // only the diagram canvas
  await page.emulateMedia({ media: 'screen' })

  await page.goto('/student/tasks')
  await expect(page.locator('[data-print-lesson]')).toHaveCount(5)
  const count = await page.locator('[data-print-lesson]').count()
  beforeRequests.length = 0
  await page.emulateMedia({ media: 'print' })
  await expect(page.locator('[data-print-lesson]')).toHaveCount(count)
  await expect(page.getByRole('button', { name: 'Показать более ранние занятия' })).toHaveCount(0)
  expect(beforeRequests).toEqual([])
  await page.screenshot({ path: testInfo.outputPath('feed-dark.png'), fullPage: true })
  if (testInfo.project.name === 'chromium') {
    await page.pdf({ path: testInfo.outputPath('worksheets.pdf'), preferCSSPageSize: true })
  }
})
