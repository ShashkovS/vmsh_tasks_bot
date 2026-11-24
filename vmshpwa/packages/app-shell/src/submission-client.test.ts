import { describe, expect, it, vi } from 'vitest'

import historyFixture from '@vmsh/contracts/fixtures/submissions/history.v1.json'
import inputFixture from '@vmsh/contracts/fixtures/submissions/input.v1.json'
import mutationFixture from '@vmsh/contracts/fixtures/submissions/mutation.v1.json'
import runtimeFixture from '@vmsh/contracts/fixtures/runtime/student.v1.json'
import {
  ApiResponseError,
  runtimeConfigSchema,
  submitTestAnswerRequestSchema,
  testAttemptCursorSchema,
} from '@vmsh/contracts'

import {
  TestSubmissionNetworkError,
  TestSubmissionProtocolError,
  TestSubmissionTimeoutError,
  createTestSubmissionClient,
} from './submission-client'

const runtime = runtimeConfigSchema.parse(runtimeFixture.response)
const request = submitTestAnswerRequestSchema.parse(mutationFixture.request)

describe('Student test-submission client', () => {
  it('posts the exact validated request and parses a strict 201 receipt', async () => {
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(
        new Response(JSON.stringify(mutationFixture.response), {
          status: 201,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )
    const client = createTestSubmissionClient(runtime, { fetchImplementation })

    await expect(client.submit(mutationFixture.response.problemId, request)).resolves.toEqual(
      mutationFixture.response,
    )
    expect(fetchImplementation).toHaveBeenCalledExactlyOnceWith(
      `/student/api/v1/problems/${mutationFixture.response.problemId}/test-attempts`,
      {
        method: 'POST',
        body: JSON.stringify(request),
        cache: 'no-store',
        credentials: 'include',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
        redirect: 'error',
        signal: expect.any(AbortSignal),
      },
    )
  })

  it('reads an encoded cursor page and rejects unsafe resource IDs before fetch', async () => {
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(
        new Response(JSON.stringify(historyFixture.response), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )
    const client = createTestSubmissionClient(runtime, { fetchImplementation })
    const cursor = testAttemptCursorSchema.parse('attempt-fixture-wrong')

    await expect(client.history(historyFixture.response.problemId, { cursor })).resolves.toEqual(
      historyFixture.response,
    )
    expect(fetchImplementation).toHaveBeenCalledWith(
      `/student/api/v1/problems/${historyFixture.response.problemId}/test-attempts?cursor=attempt-fixture-wrong`,
      expect.objectContaining({ method: 'GET' }),
    )
    await expect(client.history('../foreign')).rejects.toThrow()
    expect(fetchImplementation).toHaveBeenCalledTimes(1)
  })

  it('loads the safe current input configuration without a client-owned scope', async () => {
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(
        new Response(JSON.stringify(inputFixture.response), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )
    const client = createTestSubmissionClient(runtime, { fetchImplementation })

    await expect(client.input(inputFixture.response.problemId)).resolves.toEqual(
      inputFixture.response,
    )
    expect(fetchImplementation).toHaveBeenCalledExactlyOnceWith(
      `/student/api/v1/problems/${inputFixture.response.problemId}/test-input`,
      {
        method: 'GET',
        cache: 'no-store',
        credentials: 'include',
        headers: { Accept: 'application/json' },
        redirect: 'error',
        signal: expect.any(AbortSignal),
      },
    )
  })

  it('refreshes once and retries the byte-identical idempotent body', async () => {
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
        new Response(JSON.stringify(mutationFixture.response), {
          status: 201,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    const refreshSession = vi.fn(() => Promise.resolve())
    const client = createTestSubmissionClient(runtime, {
      fetchImplementation,
      refreshSession,
    })

    await client.submit(mutationFixture.response.problemId, request)

    expect(refreshSession).toHaveBeenCalledOnce()
    expect(fetchImplementation).toHaveBeenCalledTimes(2)
    expect(fetchImplementation.mock.calls[0]?.[1]).toMatchObject({
      method: 'POST',
      body: JSON.stringify(request),
    })
    expect(fetchImplementation.mock.calls[1]?.[1]).toMatchObject({
      method: 'POST',
      body: JSON.stringify(request),
    })
  })

  it('maps a valid correlated error and rejects malformed success/protocol status', async () => {
    const apiFailure = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            error: {
              code: 'submission_deadline_passed',
              message: 'Срок сдачи закончился',
              requestId: 'request-deadline',
            },
          }),
          { status: 409, headers: { 'Content-Type': 'application/json' } },
        ),
      ),
    )
    await expect(
      createTestSubmissionClient(runtime, { fetchImplementation: apiFailure }).submit(
        mutationFixture.response.problemId,
        request,
      ),
    ).rejects.toMatchObject({
      name: ApiResponseError.name,
      status: 409,
      code: 'submission_deadline_passed',
      requestId: 'request-deadline',
    })

    const malformed = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(new Response('{}', { status: 201 })),
    )
    await expect(
      createTestSubmissionClient(runtime, { fetchImplementation: malformed }).submit(
        mutationFixture.response.problemId,
        request,
      ),
    ).rejects.toBeInstanceOf(TestSubmissionProtocolError)

    const wrongStatus = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(new Response(JSON.stringify(mutationFixture.response), { status: 200 })),
    )
    await expect(
      createTestSubmissionClient(runtime, { fetchImplementation: wrongStatus }).submit(
        mutationFixture.response.problemId,
        request,
      ),
    ).rejects.toMatchObject({ name: TestSubmissionProtocolError.name, status: 200 })
  })

  it('distinguishes network failure from caller cancellation', async () => {
    const networkFailure = new TypeError('offline')
    const offline = createTestSubmissionClient(runtime, {
      fetchImplementation: vi.fn(() => Promise.reject(networkFailure)),
    })
    await expect(offline.submit(mutationFixture.response.problemId, request)).rejects.toMatchObject(
      {
        name: TestSubmissionNetworkError.name,
        cause: networkFailure,
      },
    )

    const abort = new DOMException('cancelled', 'AbortError')
    const cancelled = createTestSubmissionClient(runtime, {
      fetchImplementation: vi.fn(() => Promise.reject(abort)),
    })
    await expect(cancelled.history(historyFixture.response.problemId)).rejects.toBe(abort)
  })

  it('settles a fetch that never resolves after the configured deadline', async () => {
    let requestSignal: AbortSignal | undefined
    const client = createTestSubmissionClient(runtime, {
      fetchImplementation: vi.fn((_input, init) => {
        requestSignal = init?.signal ?? undefined
        return new Promise<Response>(() => undefined)
      }),
      requestTimeoutMilliseconds: 5,
    })

    await expect(client.submit(mutationFixture.response.problemId, request)).rejects.toMatchObject({
      name: TestSubmissionTimeoutError.name,
      timeoutMilliseconds: 5,
    })
    expect(requestSignal?.aborted).toBe(true)
  })
})
