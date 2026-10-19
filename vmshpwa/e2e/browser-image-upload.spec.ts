import { createHash } from 'node:crypto'
import { preparedImageSchema } from '../packages/contracts/src/image-uploads'
import { AUTH_PERSONAS, loginThroughUi } from './auth-personas'
import { expect, test, type Request } from './fixtures'

// docs/performance/browser-image-uploads.md: real worker, bounded/oriented output,
// no bytes before Send, durable metadata/bytes across reload, 1/2/10 photographs.
for (const count of [1, 2, 10]) {
  test(`browser prepares ${count} photographs and restores them without recompression`, async ({
    page,
  }, info) => {
    test.setTimeout(120_000)
    await loginThroughUi(page, AUTH_PERSONAS.student, '/student/organizers/new')
    await page.getByLabel('Сообщение организаторам').fill(`Фото ${count}: ${info.project.name}`)
    const uploads: Request[] = []
    const descriptions: unknown[] = []
    page.on('request', (request) => {
      const path = new URL(request.url()).pathname
      if (path.endsWith('/image-uploads/prepare')) descriptions.push(request.postDataJSON())
      if (path.endsWith('/organizer-questions/photos') && request.method() === 'POST')
        uploads.push(request)
    })

    const sources = await page.evaluate(async () => {
      const encode = async (type: string, width: number, height: number) => {
        const canvas = document.createElement('canvas')
        canvas.width = width
        canvas.height = height
        const context = canvas.getContext('2d')!
        context.fillStyle = '#fff'
        context.fillRect(0, 0, width, height)
        context.fillStyle = '#000'
        context.font = '48px serif'
        context.fillText('AB = BC; x² + y² = 25', 60, 100)
        const blob = await new Promise<Blob>((resolve) =>
          canvas.toBlob((value) => resolve(value!), type, 0.9),
        )
        return { bytes: [...new Uint8Array(await blob.arrayBuffer())], type: blob.type }
      }
      return [
        await encode('image/jpeg', 2600, 1300),
        await encode('image/png', 640, 360),
        await encode('image/webp', 640, 360),
      ]
    })
    const jpeg = Buffer.from(sources[0]!.bytes)
    // Minimal big-endian EXIF IFD containing Orientation=6 (90 degrees clockwise).
    const exif = Buffer.from(
      '4578696600004d4d002a00000008000101120003000000010006000000000000',
      'hex',
    )
    const app1 = Buffer.alloc(4)
    app1.writeUInt16BE(0xffe1)
    app1.writeUInt16BE(exif.length + 2, 2)
    const marker = Buffer.from('vmsh-image-source-comment')
    const comment = Buffer.alloc(4)
    comment.writeUInt16BE(0xfffe)
    comment.writeUInt16BE(marker.length + 2, 2)
    const oriented = Buffer.concat([
      jpeg.subarray(0, 2),
      app1,
      exif,
      comment,
      marker,
      jpeg.subarray(2),
    ])
    await page.locator('input[type="file"][multiple]').setInputFiles(
      Array.from({ length: count }, (_, index) => {
        const format = index % 3
        const source = sources[format]!
        return {
          name: `page-${index}.${['jpg', 'png', 'webp'][format]}`,
          mimeType: source.type,
          buffer: format === 0 ? oriented : Buffer.from(source.bytes),
        }
      }),
    )
    await expect(page.getByRole('button', { name: 'Отправить', exact: true })).toBeEnabled()
    await expect(page.getByText('Черновик сохранён на устройстве.', { exact: true })).toBeVisible()
    await expect(page.getByAltText('Выбранная фотография')).toHaveCount(count)
    expect(uploads).toHaveLength(0)
    const before = descriptions.map((value) =>
      preparedImageSchema.parse(
        Object.fromEntries(
          Object.entries(value as Record<string, unknown>).filter(
            ([key]) => !['schemaVersion', 'purpose', 'context'].includes(key),
          ),
        ),
      ),
    )
    if (info.project.name !== 'webkit') expect(before).toHaveLength(count)
    for (const [index, image] of before.entries()) {
      expect([image.width, image.height]).toEqual(index % 3 === 0 ? [960, 1920] : [640, 360])
    }
    const preparationTimings = await page.evaluate(() =>
      performance
        .getEntriesByType('measure')
        .filter((entry) => entry.name.startsWith('vmsh.image.'))
        .map(({ name, duration }) => ({ name, milliseconds: duration })),
    )
    await page.reload()
    await expect(page.getByAltText('Выбранная фотография')).toHaveCount(count)
    expect(uploads).toHaveLength(0)
    const receipt = page.waitForResponse(
      (response) =>
        response.request().method() === 'POST' &&
        new URL(response.url()).pathname === '/student/api/v1/organizer-questions',
    )
    await page.getByRole('button', { name: 'Отправить', exact: true }).click()
    expect((await receipt).status()).toBe(200)
    expect(uploads).toHaveLength(count)
    const after = descriptions.slice(before.length)
    if (before.length) {
      expect(after).toHaveLength(count)
      for (const [index, request] of uploads.entries()) {
        const image = before[index]!
        const body = request.postDataBuffer()!
        expect(body.subarray(0, 4).toString()).toBe('RIFF')
        expect(body.subarray(8, 12).toString()).toBe('WEBP')
        expect(body.length).toBe(image.byteSize)
        expect(createHash('sha256').update(body).digest('hex')).toBe(image.sha256)
        expect(body.includes(marker)).toBe(false)
        let offset = 12
        while (offset < body.length) {
          expect(['EXIF', 'XMP ', 'ANIM', 'ANMF']).not.toContain(
            body.subarray(offset, offset + 4).toString(),
          )
          const size = body.readUInt32LE(offset + 4)
          offset += 8 + size + (size & 1)
        }
        expect(after[index]).toMatchObject(image)
      }
    }
    await expect(page.locator('img[alt="Фотография в обращении"]').first()).toBeVisible()
    await page.screenshot({
      path: info.outputPath(`prepared-${count}.png`),
      animations: 'disabled',
    })
    await info.attach('image-stage-timings', {
      body: JSON.stringify([
        ...preparationTimings,
        ...(await page.evaluate(() =>
          performance
            .getEntriesByType('measure')
            .filter((entry) => entry.name.startsWith('vmsh.image.'))
            .map(({ name, duration }) => ({ name, milliseconds: duration })),
        )),
      ]),
      contentType: 'application/json',
    })
  })
}
