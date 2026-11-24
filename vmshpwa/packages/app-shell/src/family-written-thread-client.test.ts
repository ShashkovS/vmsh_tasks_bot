import { describe, expect, it, vi } from 'vitest'

import familyRuntimeFixture from '@vmsh/contracts/fixtures/runtime/family.v1.json'
import writtenFixture from '@vmsh/contracts/fixtures/submissions/written-thread.v1.json'
import { ApiResponseError, runtimeConfigSchema } from '@vmsh/contracts'

import {
  FamilyWrittenThreadProtocolError,
  createFamilyWrittenThreadClient,
} from './family-written-thread-client'

const runtime = runtimeConfigSchema.parse(familyRuntimeFixture.response)
const studentId = 'user-child-alpha'
const problemId = writtenFixture.threadResponse.problemId

function familyResponse() {
  const thread = writtenFixture.threadResponse.thread
  const entry = writtenFixture.submitResponse.entry
  return {
    ...writtenFixture.threadResponse,
    studentId,
    thread:
      thread === null
        ? null
        : {
            ...thread,
            entries: [
              {
                ...entry,
                attachments: entry.attachments.map((attachment) => ({
                  ...attachment,
                  mediaPath: attachment.mediaPath.replace(
                    '/student/api/v1/thread-entries/',
                    `/family/api/v1/children/${studentId}/thread-entries/`,
                  ),
                })),
              },
            ],
          },
  }
}

function jsonResponse(payload: unknown, status: number): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('Family written-thread client', () => {
  it('loads one child/problem projection from the Family audience path', async () => {
    const response = familyResponse()
    const fetchImplementation = vi.fn<typeof globalThis.fetch>(() =>
      Promise.resolve(jsonResponse(response, 200)),
    )
    const client = createFamilyWrittenThreadClient(runtime, { fetchImplementation })

    await expect(client.thread(studentId, problemId)).resolves.toEqual(response)
    expect(fetchImplementation).toHaveBeenCalledExactlyOnceWith(
      `/family/api/v1/children/${studentId}/problems/${problemId}/thread`,
      {
        method: 'GET',
        cache: 'no-store',
        credentials: 'include',
        headers: { Accept: 'application/json' },
        redirect: 'error',
      },
    )
  })

  it('refreshes once, rejects unsafe IDs and fails closed on a Student media path', async () => {
    const response = familyResponse()
    const fetchImplementation = vi
      .fn<typeof globalThis.fetch>()
      .mockResolvedValueOnce(
        jsonResponse(
          {
            error: {
              code: 'authentication_required',
              message: 'Войдите снова',
              requestId: 'family-thread-first',
            },
          },
          401,
        ),
      )
      .mockResolvedValueOnce(jsonResponse(response, 200))
    const refreshSession = vi.fn(() => Promise.resolve())
    const client = createFamilyWrittenThreadClient(runtime, {
      fetchImplementation,
      refreshSession,
    })

    await client.thread(studentId, problemId)
    expect(refreshSession).toHaveBeenCalledOnce()
    await expect(client.thread('../foreign', problemId)).rejects.toThrow()

    const thread = response.thread
    if (thread === null) throw new Error('Expected a thread fixture')
    const malformed = createFamilyWrittenThreadClient(runtime, {
      fetchImplementation: vi.fn(() =>
        Promise.resolve(
          jsonResponse(
            {
              ...response,
              thread: {
                ...thread,
                entries: [writtenFixture.submitResponse.entry],
              },
            },
            200,
          ),
        ),
      ),
    })
    await expect(malformed.thread(studentId, problemId)).rejects.toBeInstanceOf(
      FamilyWrittenThreadProtocolError,
    )
  })

  it('preserves the correlated forbidden response', async () => {
    const client = createFamilyWrittenThreadClient(runtime, {
      fetchImplementation: vi.fn(() =>
        Promise.resolve(
          jsonResponse(
            {
              error: {
                code: 'forbidden',
                message: 'Недостаточно прав',
                requestId: 'family-thread-forbidden',
              },
            },
            403,
          ),
        ),
      ),
    })

    await expect(client.thread(studentId, problemId)).rejects.toMatchObject({
      name: ApiResponseError.name,
      status: 403,
      code: 'forbidden',
    })
  })
})
