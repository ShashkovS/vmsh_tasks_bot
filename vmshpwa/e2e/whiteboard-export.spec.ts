import { readFile, writeFile } from 'node:fs/promises'
import { unzipSync } from 'fflate'
import { AUTH_PERSONAS, loginThroughUi } from './auth-personas'
import { expect, test } from './fixtures'

test('downloads complete PNG archive from published worksheet', async ({ page }, testInfo) => {
  test.setTimeout(120_000)
  const ids: Record<string, number> = { chromium: 34101, webkit: 34102, firefox: 34103 }
  const id = ids[testInfo.project.name]!
  const requests: string[] = []
  page.on('request', (r) => requests.push(r.url()))
  await loginThroughUi(page, AUTH_PERSONAS.teacher, '/staff/')
  expect(requests.some((r) => /whiteboard-export-generator|whiteboard-zip/.test(r))).toBe(false)
  await page.goto(`/staff/whiteboard-export?lesson=${id}`)
  await expect(page.getByRole('button', { name: 'Скачать ZIP' })).toBeVisible()
  await expect(page.getByRole('combobox', { name: 'Занятие', exact: true })).toHaveValue(String(id))
  let downloadCount = 0
  page.on('download', () => downloadCount++)
  await page.getByRole('button', { name: 'Скачать ZIP' }).click()
  await page.getByRole('button', { name: 'Отмена', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Скачать ZIP' })).toBeEnabled()
  expect(downloadCount).toBe(0)
  // Real backend remains in use: inject a transport failure only for photographs.
  await page.route('**/whiteboard-export/*/assets/*', (route) => route.abort())
  await page.getByRole('button', { name: 'Скачать ZIP' }).click()
  await expect(page.getByRole('alert')).toContainText('Задача', { timeout: 30_000 })
  expect(downloadCount).toBe(0)
  await page.unroute('**/whiteboard-export/*/assets/*')
  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Скачать ZIP' }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toBe(`math-5-7_${id}н_разбор.zip`)
  await download.saveAs(testInfo.outputPath('example.zip'))
  const files = unzipSync(await readFile(testInfo.outputPath('example.zip')))
  expect(Object.keys(files).sort()).toEqual(
    [
      `math-5-7_${id}н.01.png`,
      `math-5-7_${id}н.02.png`,
      `math-5-7_${id}н_статистика.png`,
      `math-5-7_${id}н_введение.png`,
    ].sort(),
  )
  for (const [name, bytes] of Object.entries(files)) {
    const png = Buffer.from(bytes)
    expect(png.subarray(1, 4).toString()).toBe('PNG')
    expect(png.readUInt32BE(16)).toBe(1600)
    expect(png.readUInt32BE(20)).toBeGreaterThan(100)
    await writeFile(testInfo.outputPath(name), png)
    const pixels = await page.evaluate(async (base64) => {
      const img = new Image()
      img.src = `data:image/png;base64,${base64}`
      await img.decode()
      const canvas = document.createElement('canvas')
      canvas.width = img.width
      canvas.height = img.height
      const ctx = canvas.getContext('2d')!
      ctx.drawImage(img, 0, 0)
      const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data
      let red = 0,
        ink = 0
      for (let i = 0; i < data.length; i += 4) {
        if (data[i]! > 180 && data[i + 1]! < 60 && data[i + 2]! < 110) red++
        if (data[i]! < 100 && data[i + 1]! < 100 && data[i + 2]! < 100) ink++
      }
      return { red, ink }
    }, png.toString('base64'))
    expect(pixels.ink).toBeGreaterThan(100)
    if (name.endsWith('.01.png')) expect(pixels.red).toBeGreaterThan(1000)
  }
  await page.screenshot({ path: testInfo.outputPath('page.png'), fullPage: true })
  await page.setViewportSize({ width: 360, height: 780 })
  await page.getByRole('button', { name: 'Переключить на тёмную тему' }).click()
  await page.getByLabel('Добавить статистику').uncheck()
  const second = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Скачать ZIP' }).click()
  await (await second).saveAs(testInfo.outputPath('dark-mobile.zip'))
  const dark = unzipSync(await readFile(testInfo.outputPath('dark-mobile.zip')))
  expect(Object.keys(dark)).toHaveLength(3)
  // The dimensions and layout are theme/viewport independent. Native SVG
  // rasterization may differ at a few antialiased edge pixels across captures.
  for (const [name, bytes] of Object.entries(dark)) {
    const a = Buffer.from(bytes),
      b = Buffer.from(files[name]!)
    expect(a.readUInt32BE(16)).toBe(b.readUInt32BE(16))
    expect(a.readUInt32BE(20)).toBe(b.readUInt32BE(20))
    const changed = await page.evaluate(
      async ([left, right]) => {
        async function pixels(base64: string) {
          const img = new Image()
          img.src = `data:image/png;base64,${base64}`
          await img.decode()
          const c = document.createElement('canvas')
          c.width = img.width
          c.height = img.height
          const ctx = c.getContext('2d')!
          ctx.drawImage(img, 0, 0)
          return ctx.getImageData(0, 0, c.width, c.height).data
        }
        const a = await pixels(left!),
          b = await pixels(right!)
        let count = 0
        for (let i = 0; i < a.length; i += 4)
          if (
            Math.max(
              Math.abs(a[i]! - b[i]!),
              Math.abs(a[i + 1]! - b[i + 1]!),
              Math.abs(a[i + 2]! - b[i + 2]!),
            ) > 10
          )
            count++
        return count / (a.length / 4)
      },
      [a.toString('base64'), b.toString('base64')],
    )
    expect(changed).toBeLessThan(0.001)
  }
  await page.screenshot({ path: testInfo.outputPath('mobile-dark.png'), fullPage: true })
})
