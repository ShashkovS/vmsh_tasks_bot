import { describe, expect, it, vi } from 'vitest'

import runtimeFixture from '@vmsh/contracts/fixtures/runtime/student.v1.json'
import writtenFixture from '@vmsh/contracts/fixtures/submissions/written-thread.v1.json'
import {
  ApiResponseError,
  createWrittenEntryRequestSchema,
  deleteWrittenAttachmentRequestSchema,
  reorderWrittenAttachmentsRequestSchema,
  replaceWrittenEntryRequestSchema,
  runtimeConfigSchema,
  submitWrittenEntryRequestSchema,
  writtenAttachmentUploadMetadataSchema,
} from '@vmsh/contracts'

import {
  WrittenSubmissionNetworkError,
  WrittenSubmissionProtocolError,
  createWrittenSubmissionClient,
} from './written-submission-client'

const runtime = runtimeConfigSchema.parse(runtimeFixture.response)
const createRequest = createWrittenEntryRequestSchema.parse(writtenFixture.createRequest)
const attachmentMetadata = writtenAttachmentUploadMetadataSchema.parse(
  writtenFixture.attachmentMetadata,
)

function jsonResponse(payload: unknown, status: number): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('Student written-submission client', () => {
  it('posts the exact create request and parses its strict 201 receipt', async () => {
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(jsonResponse(writtenFixture.createResponse, 201)),
    )
    const client = createWrittenSubmissionClient(runtime, { fetchImplementation })

    await expect(
      client.create(writtenFixture.createResponse.problemId, createRequest),
    ).resolves.toEqual(writtenFixture.createResponse)
    expect(fetchImplementation).toHaveBeenCalledExactlyOnceWith(
      `/student/api/v1/problems/${writtenFixture.createResponse.problemId}/thread/entries`,
      {
        method: 'POST',
        body: JSON.stringify(createRequest),
        cache: 'no-store',
        credentials: 'include',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
        redirect: 'error',
      },
    )
  })

  it('builds multipart fields without overriding the browser boundary', async () => {
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(jsonResponse(writtenFixture.attachmentResponse, 201)),
    )
    const client = createWrittenSubmissionClient(runtime, { fetchImplementation })
    const asset = new File(['webp'], 'ignored.webp', { type: 'image/webp' })

    await expect(
      client.upload(writtenFixture.createResponse.entry.entryId, {
        metadata: attachmentMetadata,
        asset,
        fileName: 'page-1.webp',
      }),
    ).resolves.toEqual(writtenFixture.attachmentResponse)

    const call = fetchImplementation.mock.calls[0]
    expect(call?.[0]).toBe(
      `/student/api/v1/thread-entries/${writtenFixture.createResponse.entry.entryId}/attachments`,
    )
    expect(call?.[1]).toMatchObject({
      method: 'POST',
      headers: { Accept: 'application/json' },
    })
    const body = call?.[1]?.body
    expect(body).toBeInstanceOf(FormData)
    const form = body as FormData
    expect(
      Object.fromEntries([...form.entries()].filter(([, value]) => typeof value === 'string')),
    ).toEqual({
      schemaVersion: '1',
      idempotencyKey: attachmentMetadata.idempotencyKey,
      expectedEntryVersion: '1',
      expectedThreadVersion: '1',
      ordinal: '0',
    })
    expect((form.get('asset') as File).name).toBe('page-1.webp')
  })

  it('loads authenticated WebP evidence for a durable replacement draft', async () => {
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(
        new Response(new Blob(['webp-bytes'], { type: 'image/webp' }), {
          status: 200,
          headers: { 'Content-Type': 'image/webp' },
        }),
      ),
    )
    const client = createWrittenSubmissionClient(runtime, { fetchImplementation })

    const media = await client.attachmentMedia('written-entry-one', 'written-attachment-one')

    expect(media.type).toBe('image/webp')
    expect(media.size).toBeGreaterThan(0)
    expect(fetchImplementation).toHaveBeenCalledExactlyOnceWith(
      '/student/api/v1/thread-entries/written-entry-one/attachments/written-attachment-one/media',
      {
        method: 'GET',
        cache: 'no-store',
        credentials: 'include',
        headers: { Accept: 'image/webp' },
        redirect: 'error',
      },
    )
  })

  it('uses exact versioned paths for reorder, delete, submit and atomic replacement', async () => {
    const fetchImplementation = vi
      .fn<typeof globalThis.fetch>()
      .mockResolvedValueOnce(jsonResponse(writtenFixture.reorderResponse, 200))
      .mockResolvedValueOnce(jsonResponse(writtenFixture.deleteResponse, 200))
      .mockResolvedValueOnce(jsonResponse(writtenFixture.submitResponse, 200))
      .mockResolvedValueOnce(jsonResponse(writtenFixture.replaceResponse, 200))
    const client = createWrittenSubmissionClient(runtime, { fetchImplementation })
    const entryId = writtenFixture.createResponse.entry.entryId
    const attachmentId = writtenFixture.attachmentResponse.entry.attachments[0]!.attachmentId
    const reorderRequest = reorderWrittenAttachmentsRequestSchema.parse(
      writtenFixture.reorderRequest,
    )
    const deleteRequest = deleteWrittenAttachmentRequestSchema.parse(writtenFixture.deleteRequest)
    const submitRequest = submitWrittenEntryRequestSchema.parse(writtenFixture.submitRequest)
    const replaceRequest = replaceWrittenEntryRequestSchema.parse(writtenFixture.replaceRequest)

    await client.reorder(entryId, reorderRequest)
    await client.deleteAttachment(entryId, attachmentId, deleteRequest)
    await client.submit(entryId, submitRequest)
    await client.replace(writtenFixture.replaceResponse.entry.entryId, replaceRequest)

    expect(
      fetchImplementation.mock.calls.map(([path, init]) => [path, init?.method, init?.body]),
    ).toEqual([
      [
        `/student/api/v1/thread-entries/${entryId}/attachments/order`,
        'PATCH',
        JSON.stringify(reorderRequest),
      ],
      [
        `/student/api/v1/thread-entries/${entryId}/attachments/${attachmentId}`,
        'DELETE',
        JSON.stringify(deleteRequest),
      ],
      [`/student/api/v1/thread-entries/${entryId}/submit`, 'POST', JSON.stringify(submitRequest)],
      [
        `/student/api/v1/thread-entries/${writtenFixture.replaceResponse.entry.entryId}/replace`,
        'POST',
        JSON.stringify(replaceRequest),
      ],
    ])
  })

  it('sets and deletes one optimistic Student reaction on a concrete review', async () => {
    const selected = {
      schemaVersion: 1 as const,
      reviewId: 'written-review-one',
      studentReaction: {
        reactionId: 0 as const,
        version: 1,
        editableUntil: '2026-09-21T11:00:00.000000Z',
        updatedAt: '2026-09-21T10:10:00.000000Z',
        deleted: false,
      },
      requestId: 'request-written-reaction-set',
    }
    const deleted = {
      ...selected,
      studentReaction: {
        ...selected.studentReaction,
        reactionId: null,
        version: 2,
        updatedAt: '2026-09-21T10:20:00.000000Z',
        deleted: true,
      },
      requestId: 'request-written-reaction-delete',
    }
    const fetchImplementation = vi
      .fn<typeof globalThis.fetch>()
      .mockResolvedValueOnce(jsonResponse(selected, 200))
      .mockResolvedValueOnce(jsonResponse(deleted, 200))
    const client = createWrittenSubmissionClient(runtime, { fetchImplementation })

    await expect(
      client.setStudentReaction('written-review-one', {
        schemaVersion: 1,
        reactionId: 0,
        expectedVersion: 0,
      }),
    ).resolves.toEqual(selected)
    await expect(
      client.deleteStudentReaction('written-review-one', {
        schemaVersion: 1,
        expectedVersion: 1,
      }),
    ).resolves.toEqual(deleted)

    expect(
      fetchImplementation.mock.calls.map(([path, init]) => [path, init?.method, init?.body]),
    ).toEqual([
      [
        '/student/api/v1/reviews/written-review-one/reaction',
        'PUT',
        JSON.stringify({ schemaVersion: 1, reactionId: 0, expectedVersion: 0 }),
      ],
      [
        '/student/api/v1/reviews/written-review-one/reaction',
        'DELETE',
        JSON.stringify({ schemaVersion: 1, expectedVersion: 1 }),
      ],
    ])
  })

  it('loads one owner-scoped thread and rejects an unsafe resource before fetch', async () => {
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(jsonResponse(writtenFixture.threadResponse, 200)),
    )
    const client = createWrittenSubmissionClient(runtime, { fetchImplementation })

    await expect(client.thread(writtenFixture.threadResponse.problemId)).resolves.toEqual(
      writtenFixture.threadResponse,
    )
    await expect(client.thread('../foreign')).rejects.toThrow()
    expect(fetchImplementation).toHaveBeenCalledTimes(1)
  })

  it('refreshes once and reuses the exact multipart body and idempotency key', async () => {
    const fetchImplementation = vi
      .fn<typeof globalThis.fetch>()
      .mockResolvedValueOnce(
        jsonResponse(
          {
            error: {
              code: 'authentication_required',
              message: 'Войдите снова',
              requestId: 'request-first',
            },
          },
          401,
        ),
      )
      .mockResolvedValueOnce(jsonResponse(writtenFixture.attachmentResponse, 201))
    const refreshSession = vi.fn(() => Promise.resolve())
    const client = createWrittenSubmissionClient(runtime, {
      fetchImplementation,
      refreshSession,
    })

    await client.upload(writtenFixture.createResponse.entry.entryId, {
      metadata: attachmentMetadata,
      asset: new File(['webp'], 'page.webp', { type: 'image/webp' }),
      fileName: 'page.webp',
    })

    expect(refreshSession).toHaveBeenCalledOnce()
    expect(fetchImplementation).toHaveBeenCalledTimes(2)
    expect(fetchImplementation.mock.calls[0]?.[1]?.body).toBe(
      fetchImplementation.mock.calls[1]?.[1]?.body,
    )
  })

  it('distinguishes correlated API, malformed protocol, network and abort failures', async () => {
    const apiFailure = createWrittenSubmissionClient(runtime, {
      fetchImplementation: vi.fn(() =>
        Promise.resolve(
          jsonResponse(
            {
              error: {
                code: 'written_entry_version_conflict',
                message: 'Черновик изменился',
                requestId: 'request-conflict',
              },
            },
            409,
          ),
        ),
      ),
    })
    await expect(
      apiFailure.create(writtenFixture.createResponse.problemId, createRequest),
    ).rejects.toMatchObject({
      name: ApiResponseError.name,
      status: 409,
      code: 'written_entry_version_conflict',
    })

    const malformed = createWrittenSubmissionClient(runtime, {
      fetchImplementation: vi.fn(() => Promise.resolve(jsonResponse({}, 201))),
    })
    await expect(
      malformed.create(writtenFixture.createResponse.problemId, createRequest),
    ).rejects.toBeInstanceOf(WrittenSubmissionProtocolError)

    const networkError = new TypeError('offline')
    const offline = createWrittenSubmissionClient(runtime, {
      fetchImplementation: vi.fn(() => Promise.reject(networkError)),
    })
    await expect(
      offline.create(writtenFixture.createResponse.problemId, createRequest),
    ).rejects.toMatchObject({ name: WrittenSubmissionNetworkError.name, cause: networkError })

    const abort = new DOMException('cancelled', 'AbortError')
    const cancelled = createWrittenSubmissionClient(runtime, {
      fetchImplementation: vi.fn(() => Promise.reject(abort)),
    })
    await expect(cancelled.thread(writtenFixture.threadResponse.problemId)).rejects.toBe(abort)
  })
})
