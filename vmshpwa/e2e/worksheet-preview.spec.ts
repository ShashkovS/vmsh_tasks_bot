import { AUTH_PERSONAS, loginThroughUi } from './auth-personas'
import { test, expect } from './fixtures'

// docs/worksheet-materials.md: real same-publication Student/Staff comparison.
test('staff preview uses the student conditions and material presentation without recording views', async ({
  page,
}, info) => {
  test.setTimeout(90_000)
  const ids: Record<string, number> = { chromium: 32101, webkit: 32102, firefox: 32103 }
  const id = ids[info.project.name]!
  await loginThroughUi(
    page,
    AUTH_PERSONAS.student,
    `/student/tasks/math-5-7/${encodeURIComponent('н')}/${id}`,
  )
  const labels = page.locator('.vmsh-subpart-label')
  await expect(labels.first()).toBeVisible()
  const texts = await labels.allTextContents()
  const studentFont = await labels.first().evaluate((el) => ({
    font: getComputedStyle(el).fontFamily,
    size: getComputedStyle(el).fontSize,
  }))
  await page.screenshot({ path: info.outputPath('student-conditions.png'), fullPage: true })
  const requests: string[] = []
  page.on('request', (request) => {
    if (request.url().includes('/reveal/')) requests.push(request.url())
  })
  await loginThroughUi(page, AUTH_PERSONAS.admin, `/staff/lessons/gl-${id}`)
  const hint = page.locator('#material-hint')
  await hint.getByRole('button', { name: 'Показать PWA и Telegram' }).click()
  await expect(hint.getByText('Подсказка для печати: проведите высоту AH.').first()).toBeVisible()
  expect(await hint.locator('.vmsh-subpart-label').allTextContents()).toEqual(texts)
  expect(
    await hint
      .locator('.vmsh-subpart-label')
      .first()
      .evaluate((el) => ({
        font: getComputedStyle(el).fontFamily,
        size: getComputedStyle(el).fontSize,
      })),
  ).toEqual(studentFont)
  await expect(hint.getByRole('button', { name: 'Открыть', exact: true }).first()).toBeDisabled()
  expect(requests).toEqual([])
  await hint.screenshot({ path: info.outputPath('staff-material.png') })
  const paper = hint.locator('.vmsh-student-feed-sheet')
  for (const width of [320, 390, 1280]) {
    await page.setViewportSize({ width, height: 900 })
    for (const theme of ['light', 'dark']) {
      await page.evaluate((theme) => {
        document.documentElement.classList.toggle('dark', theme === 'dark')
        document.documentElement.style.colorScheme = theme
      }, theme)
      await expect(paper).toBeVisible()
      expect(await paper.evaluate((el) => el.scrollWidth <= el.clientWidth + 1)).toBe(true)
      await paper.screenshot({ path: info.outputPath(`staff-${width}-${theme}.png`) })
    }
  }
})
