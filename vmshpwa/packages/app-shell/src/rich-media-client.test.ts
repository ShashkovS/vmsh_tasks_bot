import { describe, expect, it, vi } from 'vitest'

import runtimeFixture from '@vmsh/contracts/fixtures/runtime/staff.v1.json'
import { runtimeConfigSchemaForAudience } from '@vmsh/contracts'

import { createStaffRichMediaClient } from './rich-media-client'

const runtime = runtimeConfigSchemaForAudience('staff').parse(runtimeFixture.response)

describe('staff rich media client', () => {
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
