import { expect, it, vi } from 'vitest'
import { ApiResponseError, runtimeConfigSchema } from '@vmsh/contracts'
import runtimeFixture from '@vmsh/contracts/fixtures/runtime/staff.v1.json'
import fixture from '@vmsh/contracts/fixtures/review/contribution.v1.json'
import { createReviewContributionClient } from './review-contribution'

const runtime = runtimeConfigSchema.parse(runtimeFixture.response)

it('uses the Staff boundary, credentials, signal and refreshes a session once', async () => {
  const fetchImplementation = vi
    .fn<typeof fetch>()
    .mockResolvedValueOnce(Response.json({}, { status: 401 }))
    .mockResolvedValueOnce(Response.json(fixture))
  const refreshSession = vi.fn().mockResolvedValue(undefined)
  const signal = new AbortController().signal
  const client = createReviewContributionClient(runtime, { fetchImplementation, refreshSession })
  expect(await client({ course: 'c-1', lesson: 0 }, signal)).toEqual(fixture)
  expect(refreshSession).toHaveBeenCalledTimes(1)
  expect(fetchImplementation).toHaveBeenLastCalledWith(
    '/staff/api/v1/review/my-contribution?course=c-1&lesson=0',
    expect.objectContaining({ credentials: 'include', cache: 'no-store', signal }),
  )
})

it('validates failures and response contracts', async () => {
  const fetchImplementation = vi
    .fn<typeof fetch>()
    .mockResolvedValueOnce(
      Response.json(
        { error: { code: 'forbidden', message: 'Нет доступа', requestId: 'denied' } },
        { status: 403 },
      ),
    )
    .mockResolvedValueOnce(Response.json({ ...fixture, allTime: null }))
  const client = createReviewContributionClient(runtime, { fetchImplementation })
  await expect(client({})).rejects.toBeInstanceOf(ApiResponseError)
  await expect(client({})).rejects.toThrow()
})
