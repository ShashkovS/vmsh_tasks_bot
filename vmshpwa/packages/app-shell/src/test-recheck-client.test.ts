import { describe, expect, it, vi } from 'vitest'

import recheckFixture from '@vmsh/contracts/fixtures/submissions/recheck.v1.json'
import runtimeFixture from '@vmsh/contracts/fixtures/runtime/staff.v1.json'
import {
  ApiResponseError,
  recheckTestAttemptsRequestSchema,
  runtimeConfigSchema,
} from '@vmsh/contracts'

import {
  TestAttemptRecheckNetworkError,
  TestAttemptRecheckProtocolError,
  createTestAttemptRecheckClient,
} from './test-recheck-client'

const runtime = runtimeConfigSchema.parse(runtimeFixture.response)
const request = recheckTestAttemptsRequestSchema.parse(recheckFixture.request)

describe('Staff test-attempt recheck client', () => {
  it('loads the preview and posts the exact preview-bound request', async () => {
    const fetchImplementation = vi
      .fn<typeof globalThis.fetch>()
      .mockResolvedValueOnce(
        new Response(JSON.stringify(recheckFixture.preview), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(recheckFixture.response), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    const client = createTestAttemptRecheckClient(runtime, { fetchImplementation })

    await expect(client.preview(recheckFixture.preview.problemId)).resolves.toEqual(
      recheckFixture.preview,
    )
    await expect(client.recheck(recheckFixture.preview.problemId, request)).resolves.toEqual(
      recheckFixture.response,
    )
    expect(fetchImplementation).toHaveBeenNthCalledWith(
      1,
      `/staff/api/v1/problems/${recheckFixture.preview.problemId}/recheck-test-attempts`,
      {
        method: 'GET',
        cache: 'no-store',
        credentials: 'include',
        headers: { Accept: 'application/json' },
        redirect: 'error',
      },
    )
    expect(fetchImplementation).toHaveBeenNthCalledWith(
      2,
      `/staff/api/v1/problems/${recheckFixture.preview.problemId}/recheck-test-attempts`,
      {
        method: 'POST',
        body: JSON.stringify(request),
        cache: 'no-store',
        credentials: 'include',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
        redirect: 'error',
      },
    )
  })

  it('refreshes once and retries a byte-identical request body', async () => {
    const fetchImplementation = vi
      .fn<typeof globalThis.fetch>()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            error: {
              code: 'authentication_required',
              message: 'Войдите снова',
              requestId: 'request-first',
            },
          }),
          { status: 401, headers: { 'Content-Type': 'application/json' } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(recheckFixture.response), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    const refreshSession = vi.fn(() => Promise.resolve())
    const client = createTestAttemptRecheckClient(runtime, {
      fetchImplementation,
      refreshSession,
    })

    await client.recheck(recheckFixture.preview.problemId, request)

    expect(refreshSession).toHaveBeenCalledOnce()
    expect(fetchImplementation).toHaveBeenCalledTimes(2)
    expect(fetchImplementation.mock.calls[0]?.[1]).toEqual(fetchImplementation.mock.calls[1]?.[1])
  })

  it('rejects unsafe IDs, malformed success and valid correlated errors', async () => {
    const malformed = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(new Response('{}', { status: 200 })),
    )
    const malformedClient = createTestAttemptRecheckClient(runtime, {
      fetchImplementation: malformed,
    })
    await expect(malformedClient.preview('../foreign')).rejects.toThrow()
    expect(malformed).not.toHaveBeenCalled()
    await expect(malformedClient.preview(recheckFixture.preview.problemId)).rejects.toBeInstanceOf(
      TestAttemptRecheckProtocolError,
    )

    const conflict = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            error: {
              code: 'test_problem_revision_changed',
              message: 'Конфигурация задачи изменилась',
              requestId: 'request-conflict',
            },
          }),
          { status: 409, headers: { 'Content-Type': 'application/json' } },
        ),
      ),
    )
    await expect(
      createTestAttemptRecheckClient(runtime, { fetchImplementation: conflict }).recheck(
        recheckFixture.preview.problemId,
        request,
      ),
    ).rejects.toMatchObject({
      name: ApiResponseError.name,
      status: 409,
      code: 'test_problem_revision_changed',
      requestId: 'request-conflict',
    })
  })

  it('distinguishes network failure from caller cancellation', async () => {
    const networkFailure = new TypeError('offline')
    const offline = createTestAttemptRecheckClient(runtime, {
      fetchImplementation: vi.fn(() => Promise.reject(networkFailure)),
    })
    await expect(offline.preview(recheckFixture.preview.problemId)).rejects.toMatchObject({
      name: TestAttemptRecheckNetworkError.name,
      cause: networkFailure,
    })

    const abort = new DOMException('cancelled', 'AbortError')
    const cancelled = createTestAttemptRecheckClient(runtime, {
      fetchImplementation: vi.fn(() => Promise.reject(abort)),
    })
    await expect(cancelled.preview(recheckFixture.preview.problemId)).rejects.toBe(abort)
  })
})
