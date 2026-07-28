import { ApiResponseError, runtimeConfigSchema } from '@vmsh/contracts'
import { describe, expect, it, vi } from 'vitest'

import {
  createReviewQueueClient,
  ReviewQueueNetworkError,
  ReviewQueueProtocolError,
} from './review-queue-client'

const runtime = runtimeConfigSchema.parse({
  contractVersion: 1,
  audience: 'staff',
  appBase: '/staff',
  apiBase: '/staff/api/v1',
  websocketPath: '/staff/ws',
  instance: 'review-client-test',
  serverTime: '2026-10-04T12:00:00Z',
  requestId: 'runtime-request',
  features: { telegram: false, google: false, nats: false, prototype: false },
})

const branches = [
  {
    queueId: 'review-queue-one',
    problemId: 'problem-one',
    problemTitle: 'Общая задача',
    courseId: 'course-math',
    groupId: 'group-a',
    submittedAt: '2026-10-04T12:01:00.000000Z',
    leaseVersion: 1,
  },
]

const listPayload = {
  schemaVersion: 1 as const,
  items: [
    {
      queueId: 'review-queue-one',
      logicalCaseId: 'problem-one',
      student: { studentId: 'student-one', displayName: 'Анна Белова' },
      submittedAt: '2026-10-04T12:01:00.000000Z',
      branches,
      lock: null,
    },
  ],
  nextCursor: null,
  requestId: 'review-list-request',
}

const leasePayload = {
  schemaVersion: 1 as const,
  lease: {
    claimToken: 'review-claim-one',
    logicalCaseId: 'problem-one',
    student: { studentId: 'student-one', displayName: 'Анна Белова' },
    claimedAt: '2026-10-04T12:02:00.000000Z',
    expiresAt: '2026-10-04T12:32:00.000000Z',
    branches,
    evidenceBranches: [
      {
        queueId: 'review-queue-one',
        thread: {
          threadId: 'thread-one',
          threadVersion: 2,
          entries: [
            {
              entryId: 'entry-one',
              entryVersion: 2,
              entryKind: 'submission',
              text: 'Решение',
              submittedAt: '2026-10-04T12:01:00.000000Z',
              attachments: [],
            },
          ],
        },
      },
    ],
  },
  requestId: 'review-lease-request',
}

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('Staff review queue client', () => {
  it('serializes validated list filters and validates the response', async () => {
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(jsonResponse(listPayload)),
    )
    const client = createReviewQueueClient(runtime, { fetchImplementation })

    await expect(
      client.list({
        problemGroup: 'problem-one',
        sort: 'newest',
        cursor: 'review-queue-before',
      }),
    ).resolves.toEqual(listPayload)
    expect(fetchImplementation).toHaveBeenCalledExactlyOnceWith(
      '/staff/api/v1/review/items?problemGroup=problem-one&sort=newest&cursor=review-queue-before',
      {
        method: 'GET',
        cache: 'no-store',
        credentials: 'include',
        headers: { Accept: 'application/json' },
        redirect: 'error',
      },
    )
  })

  it('keeps claim ownership server-side and sends the same token for lease mutations', async () => {
    const fetchImplementation = vi.fn<typeof globalThis.fetch>((input) => {
      const path = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
      return Promise.resolve(
        jsonResponse(
          path.endsWith('/release')
            ? {
                schemaVersion: 1,
                releasedItems: 1,
                requestId: 'review-release-request',
              }
            : leasePayload,
        ),
      )
    })
    const client = createReviewQueueClient(runtime, { fetchImplementation })

    await client.claim('review-queue-one')
    await client.heartbeat('review-queue-one', 'review-claim-one')
    await expect(client.release('review-queue-one', 'review-claim-one')).resolves.toBe(1)

    expect(fetchImplementation.mock.calls.map(([path]) => path)).toEqual([
      '/staff/api/v1/review/items/review-queue-one/claim',
      '/staff/api/v1/review/items/review-queue-one/heartbeat',
      '/staff/api/v1/review/items/review-queue-one/release',
    ])
    expect(fetchImplementation.mock.calls.map(([, init]) => init?.body)).toEqual([
      '{"schemaVersion":1}',
      '{"schemaVersion":1,"claimToken":"review-claim-one"}',
      '{"schemaVersion":1,"claimToken":"review-claim-one"}',
    ])
    expect(fetchImplementation.mock.calls.every(([, init]) => init?.method === 'POST')).toBe(true)
  })

  it('retries one 401 after refresh without changing the mutation body', async () => {
    const refreshSession = vi.fn(() => Promise.resolve())
    const fetchImplementation = vi
      .fn<typeof globalThis.fetch>()
      .mockResolvedValueOnce(
        jsonResponse(
          {
            error: {
              code: 'authentication_required',
              message: 'Войдите снова',
              requestId: 'expired-request',
            },
          },
          401,
        ),
      )
      .mockResolvedValueOnce(jsonResponse(leasePayload))
    const client = createReviewQueueClient(runtime, {
      fetchImplementation,
      refreshSession,
    })

    await client.heartbeat('review-queue-one', 'review-claim-one')

    expect(refreshSession).toHaveBeenCalledOnce()
    expect(fetchImplementation).toHaveBeenCalledTimes(2)
    expect(fetchImplementation.mock.calls[0]?.[1]).toEqual(fetchImplementation.mock.calls[1]?.[1])
  })

  it('sends an exact review boundary and validates the completion receipt', async () => {
    const completion = {
      schemaVersion: 1 as const,
      review: {
        reviewId: 'review-one',
        targetThreadId: 'thread-one',
        targetProblemId: 'problem-one',
        targetThreadStatus: 'accepted' as const,
        verdict: 16,
        commentEntryId: 'comment-one',
        evidenceEntryIds: ['entry-one'],
        completedAt: '2026-10-04T12:03:00.000000Z',
        replayed: false,
      },
      requestId: 'review-complete-request',
    }
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(jsonResponse(completion)),
    )
    const client = createReviewQueueClient(runtime, { fetchImplementation })
    const request = {
      schemaVersion: 1 as const,
      claimToken: 'review-claim-one',
      idempotencyKey: 'review-complete-one',
      verdict: 16,
      comment: 'Проверено.',
      confirmWithoutComment: false,
      branches: [
        {
          queueId: 'review-queue-one',
          leaseVersion: 1,
          threadId: 'thread-one',
          threadVersion: 2,
          evidence: [{ entryId: 'entry-one', entryVersion: 2 }],
        },
      ],
    }

    await expect(client.complete('review-queue-one', request)).resolves.toEqual(completion)
    expect(fetchImplementation).toHaveBeenCalledExactlyOnceWith(
      '/staff/api/v1/review/items/review-queue-one/complete',
      {
        method: 'POST',
        cache: 'no-store',
        credentials: 'include',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
        redirect: 'error',
        body: JSON.stringify(request),
      },
    )
  })

  it('separates API, malformed-contract and network failures', async () => {
    const apiFailure = createReviewQueueClient(runtime, {
      fetchImplementation: vi.fn(() =>
        Promise.resolve(
          jsonResponse(
            {
              error: {
                code: 'review_already_claimed',
                message: 'Работу уже проверяют',
                requestId: 'conflict-request',
              },
            },
            409,
          ),
        ),
      ),
    })
    await expect(apiFailure.claim('review-queue-one')).rejects.toMatchObject({
      name: ApiResponseError.name,
      status: 409,
      code: 'review_already_claimed',
    })

    const malformed = createReviewQueueClient(runtime, {
      fetchImplementation: vi.fn(() => Promise.resolve(jsonResponse({ items: [] }))),
    })
    await expect(malformed.list()).rejects.toBeInstanceOf(ReviewQueueProtocolError)

    const networkFailure = new TypeError('offline')
    const offline = createReviewQueueClient(runtime, {
      fetchImplementation: vi.fn(() => Promise.reject(networkFailure)),
    })
    await expect(offline.list()).rejects.toMatchObject({
      name: ReviewQueueNetworkError.name,
      cause: networkFailure,
    })
  })

  it('rejects a non-Staff runtime before transport', () => {
    const studentRuntime = { ...runtime, audience: 'student' as const }
    expect(() => createReviewQueueClient(studentRuntime)).toThrow()
  })
})
