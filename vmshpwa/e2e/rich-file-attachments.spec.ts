import { staffRichFileUploadResponseSchema, staffNewsItemResponseSchema } from '@vmsh/contracts'
import contentFixture from '../../pwa_tests/fixtures/content/e2e-content-v1.json' with { type: 'json' }
import { AUTH_PERSONAS, loginThroughUi } from './auth-personas'
import { expect, test, type Locator, type Page } from './fixtures'

// docs/rich-file-attachments.md: real upload → saved AST → public reader link.
test.setTimeout(90_000)
test.describe.configure({ retries: 0 })

async function attach(page: Page, editor: Locator, filename: string, endpoint: string) {
  const bytes = Buffer.from(`Исходный файл ${filename}`, 'utf8')
  const receipt = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' && new URL(response.url()).pathname === endpoint,
  )
  await editor
    .getByLabel('Файл для прикрепления')
    .setInputFiles({ name: filename, mimeType: 'application/octet-stream', buffer: bytes })
  const response = await receipt
  expect(response.status()).toBe(201)
  const file = staffRichFileUploadResponseSchema.parse(await response.json()).file
  expect(file.filename).toBe(filename)
  expect(file.byteSize).toBe(bytes.length)
  await expect(editor.getByRole('link', { name: filename, exact: true }).first()).toHaveAttribute(
    'href',
    file.url,
  )
  return { file, bytes }
}

async function readLink(page: Page, caption: string, url: string) {
  const link = page.getByRole('link', { name: caption, exact: true }).first()
  await expect(link).toHaveAttribute('href', url)
  const popupPromise = page.waitForEvent('popup')
  await link.click()
  const popup = await popupPromise
  await expect(popup.locator('body')).toContainText('Исходный файл')
  await popup.close()
}

test('news attachment survives publication and caption editing for Student and Family', async ({
  page,
  secondaryContext,
  request,
}, testInfo) => {
  await loginThroughUi(page, AUTH_PERSONAS.admin, '/staff/news?state=all')
  const form = page
    .getByRole('button', { name: 'Запланировать публикацию' })
    .locator('xpath=ancestor::form[1]')
  await form.getByRole('combobox', { name: 'Курс', exact: true }).selectOption('c-1')
  await form.getByLabel('Markdown публикации').fill(`Новость с файлом ${testInfo.project.name}`)
  const { file, bytes } = await attach(
    page,
    form,
    `Новость [${testInfo.project.name}].txt`,
    '/staff/api/v1/rich-media/files/uploads',
  )
  await form.screenshot({ path: testInfo.outputPath('news-file-editor-staff.png') })
  await form.getByLabel('Опубликовать по московскому времени').fill('2020-08-04T17:00')
  const created = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname === '/staff/api/v1/news/local',
  )
  await form.getByRole('button', { name: 'Запланировать публикацию' }).click()
  const response = await created
  expect(response.status()).toBe(201)
  const { item } = staffNewsItemResponseSchema.parse(await response.json())

  await page
    .getByRole('button', { name: `Исправить опубликованную публикацию ${item.postId}` })
    .click()
  const dialog = page.getByRole('dialog', { name: 'Исправить опубликованную новость' })
  await expect(dialog.getByRole('button', { name: 'Прикрепить файл' })).toBeVisible()
  const caption = `Скачать материалы ${testInfo.project.name}`
  await dialog.getByLabel('Markdown публикации').fill(`[${caption}](${file.url})`)
  const saved = page.waitForResponse(
    (result) =>
      result.request().method() === 'PATCH' &&
      new URL(result.url()).pathname === `/staff/api/v1/news/${item.postId}/local`,
  )
  await dialog.getByRole('button', { name: 'Сохранить изменения' }).click()
  expect((await saved).status()).toBe(200)

  const download = await request.get(file.url)
  expect(download.status()).toBe(200)
  expect(await download.body()).toEqual(bytes)
  await loginThroughUi(page, AUTH_PERSONAS.student, `/student/news/${item.postId}`)
  await readLink(page, caption, file.url)
  const family = await secondaryContext.newPage()
  await loginThroughUi(family, AUTH_PERSONAS.family, `/family/news/${item.postId}`)
  await readLink(family, caption, file.url)
  await page.screenshot({
    path: testInfo.outputPath('news-attachment-student.png'),
    fullPage: true,
  })
})

test('broadcast banner attachment is published to Student and Family', async ({
  page,
  secondaryContext,
  request,
}, testInfo) => {
  await loginThroughUi(page, AUTH_PERSONAS.admin, '/staff/broadcasts')
  const form = page
    .getByRole('button', { name: 'Запланировать', exact: true })
    .locator('xpath=ancestor::form[1]')
  await form.getByRole('combobox', { name: 'Курс', exact: true }).selectOption('c-1')
  await form.getByLabel('Markdown публикации').fill(`Объявление с файлом ${testInfo.project.name}`)
  const { file, bytes } = await attach(
    page,
    form,
    `Рассылка (${testInfo.project.name}).txt`,
    '/staff/api/v1/rich-media/files/uploads',
  )
  await form.locator('input[type="datetime-local"]').nth(0).fill('2020-08-04T17:00')
  await form.locator('input[type="datetime-local"]').nth(1).fill('2099-08-04T17:00')
  const created = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname === '/staff/api/v1/group-banners',
  )
  await form.getByRole('button', { name: 'Запланировать', exact: true }).click()
  expect((await created).status()).toBe(201)
  expect(await (await request.get(file.url)).body()).toEqual(bytes)
  await loginThroughUi(page, AUTH_PERSONAS.student, '/student/')
  await readLink(page, file.filename, file.url)
  const family = await secondaryContext.newPage()
  await loginThroughUi(family, AUTH_PERSONAS.family, '/family/')
  await readLink(family, file.filename, file.url)
})

test('both lesson blocks retain file links through draft and publication', async ({
  page,
  secondaryContext,
  request,
}, testInfo) => {
  const target = contentFixture.targets.find(
    (candidate) => candidate.project === testInfo.project.name,
  )
  if (!target) throw new Error('Missing lesson fixture')
  await loginThroughUi(page, AUTH_PERSONAS.admin, `/staff/lessons/${target.groupLessonPublicId}`)
  const attachments = []
  for (const [position, title] of [
    ['before', 'Блок перед задачами'],
    ['after', 'Блок после задач'],
  ] as const) {
    const summary = page.locator('summary').filter({ hasText: title })
    await summary.click()
    const editor = summary.locator('xpath=ancestor::details[1]')
    await editor.getByLabel(`${title}: Markdown`).fill(`Материалы ${position}`)
    const result = await attach(
      page,
      editor,
      `${position} [${testInfo.project.name}].txt`,
      `/staff/api/v1/group-lessons/${target.groupLessonPublicId}/blocks/files/uploads`,
    )
    const saved = page.waitForResponse(
      (response) =>
        response.request().method() === 'PUT' &&
        new URL(response.url()).pathname.endsWith(`/blocks/${position}/draft`),
    )
    await editor.getByRole('button', { name: 'Сохранить черновик' }).click()
    expect((await saved).status()).toBe(200)
    const published = page.waitForResponse(
      (response) =>
        response.request().method() === 'POST' &&
        new URL(response.url()).pathname.endsWith(`/blocks/${position}/publication`),
    )
    await editor.getByRole('button', { name: 'Применить публикацию' }).click()
    expect((await published).status()).toBe(200)
    attachments.push(result)
  }
  await page.reload()
  await expect(page.locator('summary').filter({ hasText: 'Блок перед задачами' })).toContainText(
    'Опубликован',
  )
  await page.locator('summary').filter({ hasText: 'Блок перед задачами' }).click()
  await page.locator('summary').filter({ hasText: 'Блок после задач' }).click()
  await page.screenshot({
    path: testInfo.outputPath('lesson-attachments-staff.png'),
    fullPage: true,
  })
  const lessonPath = `/tasks/math-5-7/${encodeURIComponent('н')}/${target.lessonNumber}`
  await loginThroughUi(page, AUTH_PERSONAS.student, `/student${lessonPath}`)
  const family = await secondaryContext.newPage()
  await loginThroughUi(family, AUTH_PERSONAS.family, `/family${lessonPath}?child=1`)
  for (const { file, bytes } of attachments) {
    await readLink(page, file.filename, file.url)
    await readLink(family, file.filename, file.url)
    expect(await (await request.get(file.url)).body()).toEqual(bytes)
  }
})
