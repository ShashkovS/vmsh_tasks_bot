import { describe, expect, it, vi } from 'vitest'

import runtimeFixture from '@vmsh/contracts/fixtures/runtime/staff.v1.json'
import { runtimeConfigSchemaForAudience } from '@vmsh/contracts'

import { createStaffRichMediaClient } from './rich-media-client'
import { createLessonBlockClient } from './lesson-block-client'

const runtime = runtimeConfigSchemaForAudience('staff').parse(runtimeFixture.response)

describe('staff rich media client', () => {
  it.each(['rich-media', 'lesson'])(
    'uploads a file with session refresh using the %s client',
    async (scope) => {
      const attachment = {
        url: `/pwa-rich-files/${'a'.repeat(64)}/document.pdf`,
        filename: 'document.pdf',
        mimeType: 'application/pdf',
        byteSize: 3,
      }
      const fetchImplementation = vi
        .fn<typeof fetch>()
        .mockResolvedValueOnce(Response.json({}, { status: 401 }))
        .mockResolvedValueOnce(
          Response.json({ schemaVersion: 1, file: attachment, requestId: 'upload' }),
        )
      const refreshSession = vi.fn().mockResolvedValue(undefined)
      const options = { fetchImplementation, refreshSession }
      const file = new File(['pdf'], 'document.pdf', { type: 'application/pdf' })
      const result =
        scope === 'lesson'
          ? createLessonBlockClient(runtime, options).uploadFile('gl-1', file)
          : createStaffRichMediaClient(runtime, options).uploadFile(file)
      await expect(result).resolves.toEqual(attachment)
      expect(refreshSession).toHaveBeenCalledOnce()
      expect(fetchImplementation.mock.calls[1]?.[0]).toBe(
        scope === 'lesson'
          ? '/staff/api/v1/group-lessons/gl-1/blocks/files/uploads'
          : '/staff/api/v1/rich-media/files/uploads',
      )
      const request = fetchImplementation.mock.calls[1]?.[1]
      expect(request?.headers).toEqual({ Accept: 'application/json' })
      expect((request?.body as FormData).get('file')).toMatchObject({
        name: file.name,
        size: file.size,
      })
    },
  )
  it('uploads one file as multipart and returns the server-owned WebP URL', async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(
      Response.json({
        schemaVersion: 1,
        image: {
          url: 'https://cdn.example.test/rich-media/sha256/aa/picture.webp',
          mimeType: 'image/webp',
          width: 1200,
          height: 900,
        },
        requestId: 'request-upload',
      }),
    )
    const client = createStaffRichMediaClient(runtime, { fetchImplementation })

    await expect(
      client.uploadImage(new File(['picture'], 'example.png', { type: 'image/png' })),
    ).resolves.toMatchObject({ mimeType: 'image/webp', width: 1200 })

    expect(fetchImplementation.mock.calls[0]?.[0]).toBe('/staff/api/v1/rich-media/uploads')
    const request = fetchImplementation.mock.calls[0]?.[1]
    expect(request).toEqual(
      expect.objectContaining({
        method: 'POST',
        body: expect.any(FormData),
        headers: { Accept: 'application/json' },
      }),
    )
    const form = request?.body as FormData
    expect(form.get('image')).toBeInstanceOf(File)
  })
})
