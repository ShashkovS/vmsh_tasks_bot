/** docs/figure-layout.md: real API, publication boundary, keyboard and exports. */
import contentFixture from '../../pwa_tests/fixtures/content/e2e-content-v1.json' with { type: 'json' }
import { readFile, writeFile } from 'node:fs/promises'
import { unzipSync } from 'fflate'
import { figureLayoutSchema } from '../packages/contracts/src/content'
import { AUTH_PERSONAS, loginThroughUi } from './auth-personas'
import { expect, test, type Page } from './fixtures'

test.describe.configure({ retries: 0 })

const svg =
  '<svg xmlns="http://www.w3.org/2000/svg" width="140" height="80" viewBox="0 0 140 80"><rect width="140" height="80" fill="white"/><circle cx="70" cy="40" r="30" fill="red"/></svg>'
const source = String.raw`\begin{document}
\задача Первая задача $x^2=4$. \includegraphics{diagram.svg}
\пункт Первый пункт. \пункт Второй пункт. \кзадача
\задача Вторая задача. \includegraphics{diagram.svg}\кзадача
\end{document}`
const headers = { Origin: 'http://127.0.0.1:5380', 'Sec-Fetch-Site': 'same-origin' }

async function publish(page: Page) {
  const workflow = page.getByTestId('content-workflow-condition')
  await workflow.getByRole('button', { name: 'Опубликовать сейчас', exact: true }).click()
  const response = page.waitForResponse(
    (r) => r.request().method() === 'POST' && r.url().endsWith('/publications'),
  )
  await workflow.getByRole('button', { name: 'Подтвердить', exact: true }).click()
  expect((await response).status()).toBe(201)
}

test('figure placement survives reload and publishes only after confirmation', async ({
  page,
  secondaryContext,
}, testInfo) => {
  test.setTimeout(120_000)
  page.setDefaultTimeout(15_000)
  const target = contentFixture.targets.find((t) => t.project === testInfo.project.name)!
  await loginThroughUi(page, AUTH_PERSONAS.admin, `/staff/lessons/${target.groupLessonPublicId}`)
  const uploaded = await page.request.post('/staff/api/v1/content/uploads', {
    headers,
    multipart: {
      groupLessonId: target.groupLessonPublicId,
      kind: 'condition',
      logicalFilename: 'figures.tex',
      source: { name: 'figures.tex', mimeType: 'application/x-tex', buffer: Buffer.from(source) },
    },
  })
  expect(uploaded.status()).toBe(201)
  const { revisionId } = (await uploaded.json()) as { revisionId: string }
  const attached = await page.request.post(`/staff/api/v1/content/revisions/${revisionId}/assets`, {
    headers: { ...headers, 'If-Match': uploaded.headers().etag! },
    multipart: {
      logicalName: 'diagram.svg',
      kind: 'svg',
      asset: { name: 'diagram.svg', mimeType: 'image/svg+xml', buffer: Buffer.from(svg) },
    },
  })
  expect([200, 201], await attached.text()).toContain(attached.status())
  const compiled = await page.request.post(
    `/staff/api/v1/content/revisions/${revisionId}/compile`,
    { headers: { ...headers, 'If-Match': attached.headers().etag! } },
  )
  expect(compiled.status()).toBe(200)
  await page.reload()
  const workflow = page.getByTestId('content-workflow-condition')
  for (let i = 1; i <= 3; i++)
    await workflow.getByLabel(`Название, строка ${i}`, { exact: true }).fill(`Фигуры ${i}`)
  await workflow.getByRole('button', { name: 'Сохранить метаданные', exact: true }).click()
  await expect(workflow.getByText('Сопоставление и метаданные подтверждены.')).toBeVisible()
  await publish(page)
  const student = await secondaryContext.newPage()
  await loginThroughUi(
    student,
    AUTH_PERSONAS.student,
    `/student/tasks/math-5-7/${encodeURIComponent('н')}/${target.lessonNumber}`,
  )
  const publicRoute = `/student/api/v1/group-lessons/${target.groupLessonPublicId}/content/condition`
  // Read the same public content route the worksheet uses.
  const publicBefore = await student.request.get(publicRoute)
  expect(publicBefore.status()).toBe(200)
  const original: unknown = await publicBefore.json()
  await student.emulateMedia({ media: 'print' })
  await expect(student.locator('article img')).toHaveCount(2)
  await student.screenshot({ path: testInfo.outputPath('student-before.png'), fullPage: true })
  await workflow.getByRole('button', { name: 'Показать PWA и Telegram' }).click()
  const editor = workflow
    .locator('details')
    .filter({ has: page.locator('summary', { hasText: 'Расположение рисунков' }) })
  await editor.locator('summary').click()
  const row = editor.getByRole('group', { name: 'Рисунок 1', exact: true })
  await expect(row).toBeVisible()
  await row.getByLabel('Пункт', { exact: true }).selectOption('б')
  await expect
    .poll(
      async () =>
        figureLayoutSchema.parse(
          await (
            await page.request.get(`/staff/api/v1/content/revisions/${revisionId}/figure-layout`)
          ).json(),
        ).entries[0]?.targetPart,
    )
    .toBe('б')
  await row.getByRole('button', { name: 'Скрыть', exact: true }).click()
  await expect(row.getByRole('button', { name: 'Восстановить', exact: true })).toBeVisible()
  await page.reload()
  await workflow.getByRole('button', { name: 'Показать PWA и Telegram' }).click()
  await editor.locator('summary').click()
  await expect(row.getByRole('button', { name: 'Восстановить', exact: true })).toBeVisible()
  expect(await (await student.request.get(publicRoute)).json()).toEqual(original)
  await row.getByRole('button', { name: 'Восстановить', exact: true }).click()
  await expect(row.getByRole('button', { name: 'Скрыть', exact: true })).toBeVisible()
  await expect(row.getByLabel('Задача', { exact: true })).toBeEnabled()
  await row.getByLabel('Задача', { exact: true }).selectOption('2')
  await expect(row.getByLabel('Задача', { exact: true })).toHaveValue('2')
  await row.getByRole('button', { name: 'Ниже', exact: true }).click()
  await expect
    .poll(
      async () =>
        figureLayoutSchema.parse(
          await (
            await page.request.get(`/staff/api/v1/content/revisions/${revisionId}/figure-layout`)
          ).json(),
        ).entries.length,
    )
    .toBe(2)
  // Keep only one of the two repeated uses; the file remains available.
  await row.getByRole('button', { name: 'Скрыть', exact: true }).click()
  await expect(row.getByRole('button', { name: 'Восстановить', exact: true })).toBeVisible()
  for (const width of [1280, 320, 390]) {
    await page.setViewportSize({ width, height: 850 })
    for (const theme of ['light', 'dark']) {
      await page.emulateMedia({ colorScheme: theme as 'light' | 'dark' })
      await page.evaluate(
        (t) => document.documentElement.classList.toggle('dark', t === 'dark'),
        theme,
      )
      await row.getByRole('button', { name: 'Восстановить', exact: true }).scrollIntoViewIfNeeded()
      await expect(row.getByRole('button', { name: 'Восстановить', exact: true })).toBeInViewport()
      expect(await editor.evaluate((e) => e.scrollWidth <= e.clientWidth + 2)).toBe(true)
      await editor.screenshot({ path: testInfo.outputPath(`editor-${width}-${theme}.png`) })
    }
  }
  await row.getByRole('button', { name: 'Восстановить', exact: true }).focus()
  await page.keyboard.press('Enter')
  await expect(row.getByRole('button', { name: 'Скрыть', exact: true })).toBeVisible()
  await row.getByRole('button', { name: 'Скрыть', exact: true }).click()
  await publish(page)
  expect(await (await student.request.get(publicRoute)).json()).not.toEqual(original)
  await student.reload()
  await student.emulateMedia({ media: 'print' })
  await expect(student.locator('article img')).toHaveCount(1)
  await expect(student.getByText('Расположение рисунков', { exact: true })).toHaveCount(0)
  await student.screenshot({ path: testInfo.outputPath('student-print.png'), fullPage: true })
  await page.goto(`/staff/whiteboard-export?lesson=${target.lessonNumber}`)
  await page.getByLabel('Добавить статистику').uncheck()
  const downloading = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Скачать ZIP', exact: true }).click()
  const download = await downloading
  await download.saveAs(testInfo.outputPath('figures.zip'))
  const files = unzipSync(await readFile(testInfo.outputPath('figures.zip')))
  expect(Object.keys(files)).toHaveLength(2)
  for (const [name, bytes] of Object.entries(files)) {
    const png = Buffer.from(bytes)
    expect(png.readUInt32BE(16)).toBe(1600)
    const redPixels = await page.evaluate(async (base64) => {
      const img = new Image()
      img.src = `data:image/png;base64,${base64}`
      await img.decode()
      const canvas = document.createElement('canvas')
      canvas.width = img.width
      canvas.height = img.height
      const ctx = canvas.getContext('2d')!
      ctx.drawImage(img, 0, 0)
      const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data
      let red = 0
      for (let i = 0; i < data.length; i += 4)
        if (data[i]! > 180 && data[i + 1]! < 90 && data[i + 2]! < 90) red++
      return red
    }, png.toString('base64'))
    if (name.endsWith('.01.png')) expect(redPixels).toBe(0)
    else expect(redPixels).toBeGreaterThan(100)
    await writeFile(testInfo.outputPath(name), png)
  }
})
