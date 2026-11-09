/** docs/figure-layout.md: real API, publication boundary, keyboard and exports. */
import contentFixture from '../../pwa_tests/fixtures/content/e2e-content-v1.json' with { type: 'json' }
import type { Locator } from './fixtures'
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

async function setMetadataTitle(page: Page, workflow: Locator, row: number, value: string) {
  await workflow.getByRole('gridcell', { name: `Название, строка ${row}`, exact: true }).dblclick()
  const dialog = page.getByRole('dialog')
  await dialog.getByRole('textbox', { name: 'Название', exact: true }).fill(value)
  await dialog.getByRole('button', { name: 'Применить' }).click()
}

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
  test.setTimeout(180_000)
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
  // A previous publication may use different item identities. Explicitly map
  // this fixture's three items before editing their metadata.
  const matching = workflow.getByRole('region', { name: 'Сопоставление задач', exact: true })
  await expect(
    matching.or(workflow.getByRole('heading', { name: 'Метаданные задач', exact: true })).first(),
  ).toBeVisible()
  if (await matching.isVisible()) {
    for (const select of await matching.getByRole('combobox').all()) {
      await select.selectOption('insert_new')
    }
    await matching.getByRole('button', { name: 'Подтвердить сопоставление' }).click()
  }
  for (let i = 1; i <= 3; i++) await setMetadataTitle(page, workflow, i, `Фигуры ${i}`)
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
  const layoutRoute = `/staff/api/v1/content/revisions/${revisionId}/figure-layout`
  const layout = async () =>
    figureLayoutSchema.parse(await (await page.request.get(layoutRoute)).json())
  const firstId = (await layout()).figures[0]!.occurrenceId
  const controls = workflow.locator(`[data-figure-controls="${firstId}"]`)
  const figure = controls.locator('xpath=ancestor::figure')
  const open = async (name: string) => {
    await page.keyboard.press('Escape')
    await controls.getByRole('button', { name: new RegExp(`^${name}:`) }).click()
    const dialog = page.getByRole('dialog', { name, exact: true })
    await expect(dialog).toBeVisible()
    await expect(dialog).toHaveCSS('opacity', '1')
    return dialog
  }
  const sizingButton = controls.getByRole('button', { name: /^Размер и размещение:/ })
  await sizingButton.focus()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('dialog', { name: 'Размер и размещение', exact: true })).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(sizingButton).toBeFocused()
  expect((await layout()).entries).toEqual([])
  const size = await open('Размер и размещение')
  await size.getByRole('spinbutton', { name: 'Ширина, rem' }).fill('12')
  await size.getByRole('spinbutton', { name: 'Ширина, rem' }).blur()
  await expect.poll(async () => (await layout()).entries[0]?.widthRem).toBe(12)
  await page.keyboard.press('Escape')
  expect(await (await student.request.get(publicRoute)).json()).toEqual(original)
  await page.reload()
  await expect(
    workflow.getByText('Есть неопубликованные изменения оформления рисунков.', { exact: true }),
  ).toBeVisible()
  await publish(page)
  const resized = (await (await student.request.get(publicRoute)).json()) as {
    publicationId: string
    revisionId: string
  }
  expect(resized.revisionId).toBe(revisionId)
  await expect(student.locator('article figure').first()).toHaveCSS('width', '192px')
  await student.reload()
  await expect(student.locator('article figure').first()).toHaveCSS('width', '192px')
  await expect(
    workflow.getByText('Есть неопубликованные изменения оформления рисунков.', { exact: true }),
  ).toHaveCount(0)
  await workflow.getByRole('button', { name: 'Показать PWA и Telegram' }).click()
  for (const placement of [
    'center-source',
    'center-before',
    'center-after',
    'float-right',
    'float-left',
  ]) {
    const dialog = await open('Размер и размещение')
    await dialog.getByLabel('Размещение', { exact: true }).selectOption(placement)
    await expect.poll(async () => (await layout()).entries[0]?.placement).toBe(placement)
    await page.keyboard.press('Escape')
    if (placement.startsWith('float-'))
      await expect(figure).toHaveAttribute('data-float-hint', placement.slice(6))
    else await expect(figure).toHaveAttribute('data-centered', 'true')
  }
  // Absolute sizing: huge figures fit the available area, tiny figures keep usable controls below.
  for (const widthRem of [80, 0.5, 12]) {
    const dialog = await open('Размер и размещение')
    await dialog.getByRole('spinbutton', { name: 'Ширина, rem' }).fill(String(widthRem))
    await dialog.getByRole('spinbutton', { name: 'Ширина, rem' }).blur()
    await expect.poll(async () => (await layout()).entries[0]?.widthRem).toBe(widthRem)
    await page.keyboard.press('Escape')
    if (widthRem === 0.5) await expect(figure).toHaveAttribute('data-editor-small', 'true')
    expect(
      await figure.evaluate(
        (el) => el.getBoundingClientRect().width <= el.parentElement!.clientWidth + 2,
      ),
    ).toBe(true)
  }
  for (const width of [1280, 320, 390]) {
    await page.setViewportSize({ width, height: 850 })
    for (const theme of ['light', 'dark']) {
      await page.evaluate(
        (t) => document.documentElement.classList.toggle('dark', t === 'dark'),
        theme,
      )
      const dialog = await open('Размер и размещение')
      expect(await dialog.evaluate((e) => e.scrollWidth <= e.clientWidth + 2)).toBe(true)
      await page.screenshot({
        path: testInfo.outputPath(`editor-${width}-${theme}.png`),
        animations: 'disabled',
      })
      await page.keyboard.press('Escape')
      if (width < 512) await expect(figure).not.toHaveAttribute('data-float-hint')
    }
  }
  await page.setViewportSize({ width: 1280, height: 850 })
  await page.evaluate(() => {
    document.documentElement.style.fontSize = '200%'
  })
  const zoomDialog = await open('Размер и размещение')
  expect(await zoomDialog.evaluate((e) => e.scrollWidth <= e.clientWidth + 2)).toBe(true)
  await page.screenshot({
    path: testInfo.outputPath('editor-200-percent.png'),
    animations: 'disabled',
  })
  await page.keyboard.press('Escape')
  await page.evaluate(() => {
    document.documentElement.style.fontSize = ''
  })
  const sourcePosition = await open('Размер и размещение')
  await sourcePosition.getByLabel('Размещение', { exact: true }).selectOption('center-source')
  await expect.poll(async () => (await layout()).entries[0]?.placement).toBe('center-source')
  await page.keyboard.press('Escape')
  let actions = await open('Действия с рисунком')
  await expect(actions.getByRole('button', { name: 'В предыдущую задачу' })).toBeDisabled()
  await actions.locator('summary').click()
  await actions.getByLabel('Пункт', { exact: true }).selectOption('б')
  await expect.poll(async () => (await layout()).entries[0]?.targetPart).toBe('б')
  expect((await layout()).entries[0]?.placement).toBe('center-before')
  actions = await open('Действия с рисунком')
  await actions.getByRole('button', { name: 'В следующую задачу' }).click()
  await expect.poll(async () => (await layout()).entries[0]?.targetOrdinal).toBe(2)
  expect((await layout()).entries[0]?.targetPart).toBeNull()
  actions = await open('Действия с рисунком')
  await expect(actions.getByRole('button', { name: 'В следующую задачу' })).toBeDisabled()
  await actions.getByRole('button', { name: 'В предыдущую задачу' }).click()
  await expect.poll(async () => (await layout()).entries[0]?.targetOrdinal).toBe(1)
  actions = await open('Действия с рисунком')
  await actions.getByRole('button', { name: 'В следующую задачу' }).click()
  await expect.poll(async () => (await layout()).entries[0]?.targetOrdinal).toBe(2)
  actions = await open('Действия с рисунком')
  await actions.getByRole('button', { name: 'Скрыть рисунок' }).click()
  const restore = workflow.getByRole('button', { name: 'Восстановить', exact: true })
  await expect(restore).toBeVisible()
  await restore.focus()
  await page.keyboard.press('Enter')
  await expect(controls).toBeVisible()
  actions = await open('Действия с рисунком')
  await actions.getByRole('button', { name: 'Скрыть рисунок' }).click()
  await expect(restore).toBeVisible()
  // The other occurrence of the same SVG is still visible and unchanged.
  expect((await layout()).entries).toHaveLength(1)
  expect(await (await student.request.get(publicRoute)).json()).toEqual(resized)
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
  // hint-preview-empty-materials-20261004.md: exercise the actual file workflow,
  // excluded solution assets, shared editor, and missing independent materials.
  await page.goto(`/staff/lessons/${target.groupLessonPublicId}`)
  const hintWorkflow = page.getByTestId('content-workflow-hint')
  const hintSource = String.raw`\begin{document}
\задача Первая задача $x^2=4$. \includegraphics{diagram.svg}
\пункт Первый пункт. \пункт Второй пункт. \кзадача
\подсказка \пунктн{а} Совет для первого пункта. \пунктн{б} \кподсказка
\задача Вторая задача. \includegraphics{diagram.svg}\кзадача
\решение \includegraphics{excluded-solution.svg}\крешение
\end{document}`
  await hintWorkflow.getByLabel('LaTeX-файл').setInputFiles({
    name: 'hint-figures.tex',
    mimeType: 'application/x-tex',
    buffer: Buffer.from(hintSource),
  })
  const hintUpload = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname === '/staff/api/v1/content/uploads',
  )
  await hintWorkflow.getByRole('button', { name: 'Загрузить и проверить' }).click()
  const hintUploaded = await hintUpload
  expect(hintUploaded.status()).toBe(201)
  const { revisionId: hintRevisionId } = (await hintUploaded.json()) as { revisionId: string }
  const hintMatching = hintWorkflow.getByRole('region', {
    name: 'Сопоставление задач',
    exact: true,
  })
  const hintReviewed = hintWorkflow.getByText(
    'Сопоставление задач подтверждено; метаданные берутся из условия.',
  )
  await expect(hintMatching.or(hintReviewed).first()).toBeVisible()
  if (await hintMatching.isVisible()) {
    for (const select of await hintMatching.getByRole('combobox').all()) {
      await select.selectOption({ index: 1 })
    }
    await hintMatching.getByRole('button', { name: 'Подтвердить сопоставление' }).click()
  }
  await expect(
    hintWorkflow.getByText('Сопоставление задач подтверждено; метаданные берутся из условия.'),
  ).toBeVisible()
  const showHintPreview = hintWorkflow.getByRole('button', { name: 'Показать PWA и Telegram' })
  if (await showHintPreview.isVisible()) await showHintPreview.click()
  await expect(hintWorkflow.getByText('Совет для первого пункта.', { exact: true })).toBeVisible()
  await expect(hintWorkflow.getByRole('button', { name: 'Подсказка', exact: true })).toHaveCount(1)
  await expect(hintWorkflow.getByRole('button', { name: 'Решение', exact: true })).toHaveCount(0)
  const hintLayoutRoute = `/staff/api/v1/content/revisions/${hintRevisionId}/figure-layout`
  const hintLayout = async () =>
    figureLayoutSchema.parse(await (await page.request.get(hintLayoutRoute)).json())
  const hintId = (await hintLayout()).figures[0]!.occurrenceId
  const hintControls = hintWorkflow.locator(`[data-figure-controls="${hintId}"]`).first()
  await hintControls.getByRole('button', { name: /^Размер и размещение:/ }).click()
  const hintSize = page.getByRole('dialog', { name: 'Размер и размещение', exact: true })
  await hintSize.getByRole('spinbutton', { name: 'Ширина, rem' }).fill('10')
  await hintSize.getByRole('spinbutton', { name: 'Ширина, rem' }).blur()
  await expect.poll(async () => (await hintLayout()).entries[0]?.widthRem).toBe(10)
  await hintSize.getByLabel('Размещение', { exact: true }).selectOption('float-left')
  await expect.poll(async () => (await hintLayout()).entries[0]?.placement).toBe('float-left')
  await page.keyboard.press('Escape')
  await hintControls.getByRole('button', { name: /^Действия с рисунком:/ }).click()
  await page
    .getByRole('dialog', { name: 'Действия с рисунком', exact: true })
    .getByRole('button', { name: 'Скрыть рисунок' })
    .click()
  await hintWorkflow.getByRole('button', { name: 'Восстановить', exact: true }).click()
  await expect(hintControls).toBeVisible()
  await page.reload()
  await hintWorkflow.getByRole('button', { name: 'Показать PWA и Telegram' }).click()
  expect((await hintLayout()).entries[0]).toMatchObject({
    widthRem: 10,
    placement: 'float-left',
    hidden: false,
  })
  for (const theme of ['light', 'dark']) {
    await page.setViewportSize({ width: 320, height: 850 })
    await page.evaluate(
      (value) => document.documentElement.classList.toggle('dark', value === 'dark'),
      theme,
    )
    await hintWorkflow.screenshot({ path: testInfo.outputPath(`hint-preview-320-${theme}.png`) })
  }
  await page.setViewportSize({ width: 1280, height: 850 })
  await hintWorkflow.getByRole('button', { name: 'Опубликовать сейчас', exact: true }).click()
  const hintPublishing = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' && response.url().endsWith('/publications'),
  )
  await hintWorkflow.getByRole('button', { name: 'Подтвердить', exact: true }).click()
  expect((await hintPublishing).status()).toBe(201)
  await student.emulateMedia({ media: 'screen' })
  await student.reload()
  await expect(student.getByRole('button', { name: 'Подсказка', exact: true })).toHaveCount(1)
  await expect(student.getByRole('button', { name: 'Решение', exact: true })).toHaveCount(0)
})
