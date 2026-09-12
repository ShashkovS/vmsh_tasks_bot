import { describe, expect, it, vi } from 'vitest'

import runtimeFixture from '@vmsh/contracts/fixtures/runtime/staff.v1.json'
import writtenFixture from '@vmsh/contracts/fixtures/submissions/written-thread.v1.json'
import { ApiResponseError, runtimeConfigSchema } from '@vmsh/contracts'

import {
  WrittenMaterialReassignmentNetworkError,
  WrittenMaterialReassignmentProtocolError,
  createWrittenMaterialReassignmentClient,
} from './written-material-reassignment-client'

const runtime = runtimeConfigSchema.parse(runtimeFixture.response)
const sourceEntry = writtenFixture.submitResponse.entry
const sourceAttachmentFixture = sourceEntry.attachments.at(0)
if (!sourceAttachmentFixture) throw new Error('Written fixture must contain one attachment')
const sourceAttachment = {
  ...sourceAttachmentFixture,
  mediaPath:
    '/staff/api/v1/thread-entries/written-entry-fixture-1/attachments/written-attachment-fixture-1/media',
}
const selectedItem = {
  entryId: sourceEntry.entryId,
  itemKind: 'attachment' as const,
  attachmentId: sourceAttachment.attachmentId,
}
const previewRequest = {
  schemaVersion: 1 as const,
  sourceThreadId: writtenFixture.submitResponse.threadId,
  targetProblemId: 'problem-written-target',
  items: [selectedItem],
}
const scope = {
  courseId: 'course-math',
  groupId: 'group-beginner',
  groupLessonId: 'group-lesson-41',
}
const previewResponse = {
  schemaVersion: 1 as const,
  studentId: 'user-student',
  source: {
    threadId: previewRequest.sourceThreadId,
    problemId: writtenFixture.submitResponse.problemId,
    threadStatus: 'awaiting_review' as const,
    threadVersion: writtenFixture.submitResponse.threadVersion,
    scope,
  },
  target: {
    threadId: null,
    problemId: previewRequest.targetProblemId,
    threadVersion: null,
    scope,
  },
  items: [
    {
      ...selectedItem,
      entryState: 'submitted' as const,
      text: null,
      attachment: sourceAttachment,
      locked: false,
    },
  ],
  impact: {
    postReview: false,
    sourceEvidenceUnchanged: true as const,
    sourceVerdictUnchanged: true as const,
    targetRequiresReview: true as const,
    studentLabel: 'Перенесено преподавателем' as const,
  },
  requestId: 'request-preview',
}
const reassignRequest = {
  ...previewRequest,
  idempotencyKey: 'f9a98ed8-4c1a-4c5e-baf9-82e57c9fe234',
  expectedSourceThreadVersion: previewResponse.source.threadVersion,
  expectedTargetThreadVersion: null,
  reason: 'Работа приложена к соседней задаче.',
}
const reassignResponse = {
  schemaVersion: 1 as const,
  reassignmentId: 'written-reassignment-1',
  source: {
    threadId: previewResponse.source.threadId,
    problemId: previewResponse.source.problemId,
    threadStatus: 'closed' as const,
    threadVersion: previewResponse.source.threadVersion + 1,
  },
  target: {
    threadId: 'written-thread-target',
    problemId: previewResponse.target.problemId,
    threadStatus: 'awaiting_review' as const,
    threadVersion: 1,
  },
  items: previewRequest.items,
  movedAt: '2026-09-20T13:05:00Z',
  studentLabel: 'Перенесено преподавателем' as const,
  requestId: 'request-commit',
}

describe('Staff written-material reassignment client', () => {
  it('posts strict preview and commit bodies to Staff endpoints', async () => {
    const fetchImplementation = vi
      .fn<typeof globalThis.fetch>()
      .mockResolvedValueOnce(
        new Response(JSON.stringify(previewResponse), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(reassignResponse), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    const client = createWrittenMaterialReassignmentClient(runtime, { fetchImplementation })

    await expect(client.preview(previewRequest)).resolves.toEqual(previewResponse)
    await expect(client.reassign(reassignRequest)).resolves.toEqual(reassignResponse)
    expect(fetchImplementation).toHaveBeenNthCalledWith(
      1,
      '/staff/api/v1/submission-material-reassignments/preview',
      {
        method: 'POST',
        body: JSON.stringify(previewRequest),
        cache: 'no-store',
        credentials: 'include',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
        redirect: 'error',
      },
    )
    expect(fetchImplementation).toHaveBeenNthCalledWith(
      2,
      '/staff/api/v1/submission-material-reassignments',
      {
        method: 'POST',
        body: JSON.stringify(reassignRequest),
        cache: 'no-store',
        credentials: 'include',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
        redirect: 'error',
      },
    )
  })

  it('refreshes once and retries byte-identical commit and media requests', async () => {
    const unauthorized = () =>
      new Response(
        JSON.stringify({
          error: {
            code: 'authentication_required',
            message: 'Войдите снова',
            requestId: 'request-auth',
          },
        }),
        { status: 401, headers: { 'Content-Type': 'application/json' } },
      )
    const fetchImplementation = vi
      .fn<typeof globalThis.fetch>()
      .mockResolvedValueOnce(unauthorized())
      .mockResolvedValueOnce(
        new Response(JSON.stringify(reassignResponse), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
      .mockResolvedValueOnce(unauthorized())
      .mockResolvedValueOnce(
        new Response(new Blob(['webp'], { type: 'image/webp' }), {
          status: 200,
          headers: { 'Content-Type': 'image/webp' },
        }),
      )
    const refreshSession = vi.fn(() => Promise.resolve())
    const client = createWrittenMaterialReassignmentClient(runtime, {
      fetchImplementation,
      refreshSession,
    })

    await client.reassign(reassignRequest)
    const media = await client.attachmentMedia(sourceEntry.entryId, sourceAttachment.attachmentId)

    expect(media.type).toBe('image/webp')
    expect(refreshSession).toHaveBeenCalledTimes(2)
    expect(fetchImplementation.mock.calls[0]?.[1]).toEqual(fetchImplementation.mock.calls[1]?.[1])
    expect(fetchImplementation.mock.calls[2]?.[1]).toEqual(fetchImplementation.mock.calls[3]?.[1])
  })

  it('rejects unsafe IDs, malformed success and correlated conflicts', async () => {
    const malformed = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(new Response('{}', { status: 200 })),
    )
    const malformedClient = createWrittenMaterialReassignmentClient(runtime, {
      fetchImplementation: malformed,
    })
    await expect(malformedClient.attachmentMedia('../foreign', 'attachment-one')).rejects.toThrow()
    expect(malformed).not.toHaveBeenCalled()
    await expect(malformedClient.preview(previewRequest)).rejects.toBeInstanceOf(
      WrittenMaterialReassignmentProtocolError,
    )

    const conflict = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            error: {
              code: 'written_submission_version_conflict',
              message: 'Переписка изменилась',
              requestId: 'request-conflict',
            },
          }),
          { status: 409, headers: { 'Content-Type': 'application/json' } },
        ),
      ),
    )
    await expect(
      createWrittenMaterialReassignmentClient(runtime, {
        fetchImplementation: conflict,
      }).reassign(reassignRequest),
    ).rejects.toMatchObject({
      name: ApiResponseError.name,
      status: 409,
      code: 'written_submission_version_conflict',
      requestId: 'request-conflict',
    })
  })

  it('distinguishes network failure from caller cancellation', async () => {
    const networkFailure = new TypeError('offline')
    const offline = createWrittenMaterialReassignmentClient(runtime, {
      fetchImplementation: vi.fn(() => Promise.reject(networkFailure)),
    })
    await expect(offline.preview(previewRequest)).rejects.toMatchObject({
      name: WrittenMaterialReassignmentNetworkError.name,
      cause: networkFailure,
    })

    const abort = new DOMException('cancelled', 'AbortError')
    const cancelled = createWrittenMaterialReassignmentClient(runtime, {
      fetchImplementation: vi.fn(() => Promise.reject(abort)),
    })
    await expect(cancelled.preview(previewRequest)).rejects.toBe(abort)
  })
})
