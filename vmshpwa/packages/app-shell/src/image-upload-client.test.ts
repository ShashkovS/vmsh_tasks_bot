import { describe, expect, it, vi } from 'vitest'
import {
  ApiResponseError,
  preparedImageSchema,
  runtimeConfigSchemaForAudience,
} from '@vmsh/contracts'
import runtimeFixture from '@vmsh/contracts/fixtures/runtime/student.v1.json'
import { ImageUploadClient } from './image-upload-client'

// docs/performance/browser-image-uploads.md: no bytes before Send and no GET.
const runtime = runtimeConfigSchemaForAudience('student').parse(runtimeFixture.response)
const metadata = {
  clientId: 'bb9772f5-6754-44e3-a3c0-c6937d289dd6',
  filename: 'page.webp',
  sha256: '00'.repeat(32),
  byteSize: 4,
  width: 100,
  height: 200,
}
const uploadId = '4f898c3c-4a95-4a75-acb8-f2dd1db60b85'
function grant(transport: 's3' | 'proxy' = 's3') {
  return {
    schemaVersion: 1,
    uploadId,
    transport,
    expiresAt: new Date(Date.now() + 600_000).toISOString(),
    ...(transport === 's3'
      ? {
          method: 'PUT',
          url: 'https://s3.example.test/prepared?signature=secret',
          headers: { 'Content-Type': 'image/webp', 'x-amz-checksum-sha256': `${'A'.repeat(43)}=` },
        }
      : {}),
  }
}
const error = (code: string, status = 409) =>
  Response.json(
    { schemaVersion: 1, error: { code, message: 'Повторите отправку', requestId: 'image-error' } },
    { status },
  )
const blob = new Blob(['webp'], { type: 'image/webp' })

describe('checksum-bound image upload', () => {
  it('prefetches only control data and uploads the exact Blob on Send', async () => {
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(Response.json(grant()))
      .mockResolvedValueOnce(new Response(null, { status: 200 }))
      .mockResolvedValueOnce(Response.json({ photoId: 'sup-1' }))
    const client = new ImageUploadClient(runtime, 'support', {}, { fetchImplementation })
    client.prefetch(metadata)
    await vi.waitFor(() => expect(fetchImplementation).toHaveBeenCalledTimes(1))
    const proxy = vi.fn()
    const result = await client.upload(
      blob,
      metadata,
      '/questions/photos',
      (payload) => payload,
      proxy,
    )
    expect(result).toEqual({ photoId: 'sup-1' })
    expect(proxy).not.toHaveBeenCalled()
    expect(fetchImplementation.mock.calls.map((call) => call[1]?.method)).toEqual([
      'POST',
      'PUT',
      'POST',
    ])
    const put = fetchImplementation.mock.calls[1]?.[1]
    expect(put?.body).toBe(blob)
    expect(put?.credentials).toBe('omit')
    expect(put?.headers).not.toHaveProperty('Content-Length')
    expect(JSON.parse(fetchImplementation.mock.calls[2]?.[1]?.body as string)).toEqual({
      schemaVersion: 1,
      uploadId,
    })
  })

  it('finalizes a lost PUT acknowledgment before sending any bytes again', async () => {
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(Response.json(grant()))
      .mockRejectedValueOnce(new TypeError('lost PUT acknowledgment'))
      .mockResolvedValueOnce(Response.json({ photoId: 'sup-1' }))
    const client = new ImageUploadClient(runtime, 'support', {}, { fetchImplementation })
    await client.upload(blob, metadata, '/questions/photos', (payload) => payload, vi.fn())
    expect(fetchImplementation).toHaveBeenCalledTimes(3)
  })

  it('renews and retries a missing object, then uses the same intent for proxy fallback', async () => {
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(Response.json(grant()))
      .mockRejectedValueOnce(new TypeError('CORS'))
      .mockResolvedValueOnce(error('image_upload_not_uploaded'))
      .mockResolvedValueOnce(Response.json(grant()))
      .mockRejectedValueOnce(new TypeError('CORS'))
      .mockResolvedValueOnce(error('image_upload_not_uploaded'))
    const proxy = vi.fn().mockResolvedValue({ photoId: 'sup-1' })
    const client = new ImageUploadClient(runtime, 'support', {}, { fetchImplementation })
    await expect(
      client.upload(blob, metadata, '/questions/photos', (payload) => payload, proxy),
    ).resolves.toEqual({ photoId: 'sup-1' })
    expect(fetchImplementation.mock.calls[3]?.[0]).toBe(
      `${runtime.apiBase}/image-uploads/${uploadId}/renew`,
    )
    expect(proxy).toHaveBeenCalledWith({
      'X-Vmsh-Prepared-WebP': '1',
      'X-Vmsh-Image-Upload': uploadId,
    })
  })

  it('does not hide an ownership or integrity failure behind proxy upload', async () => {
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(Response.json(grant()))
      .mockResolvedValueOnce(new Response())
      .mockResolvedValueOnce(error('image_upload_integrity_mismatch', 422))
    const proxy = vi.fn()
    const client = new ImageUploadClient(runtime, 'support', {}, { fetchImplementation })
    await expect(
      client.upload(blob, metadata, '/questions/photos', (payload) => payload, proxy),
    ).rejects.toBeInstanceOf(ApiResponseError)
    expect(proxy).not.toHaveBeenCalled()
  })

  it('restores durable metadata with a new client and retains domain binding', async () => {
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(Response.json({ schemaVersion: 1, uploadId, transport: 'completed' }))
      .mockResolvedValueOnce(Response.json({ attachmentId: 'attachment-1' }))
    const client = new ImageUploadClient(
      runtime,
      'written',
      { problemId: 'problem-1' },
      { fetchImplementation },
    )
    const binding = {
      ordinal: 0,
      expectedEntryVersion: 1,
      expectedThreadVersion: 2,
      idempotencyKey: metadata.clientId,
    }
    await client.upload(
      blob,
      preparedImageSchema.parse(JSON.parse(JSON.stringify(metadata))),
      '/thread-entries/entry-1/attachments',
      (payload) => payload,
      vi.fn(),
      binding,
    )
    expect(fetchImplementation.mock.calls.map((call) => call[1]?.method)).toEqual(['POST', 'POST'])
    expect(JSON.parse(fetchImplementation.mock.calls[1]?.[1]?.body as string)).toEqual({
      schemaVersion: 1,
      uploadId,
      ...binding,
    })
  })
})
