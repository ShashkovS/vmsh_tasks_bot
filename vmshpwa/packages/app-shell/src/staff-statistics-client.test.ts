import { describe, expect, it, vi } from 'vitest'

import runtimeFixture from '@vmsh/contracts/fixtures/runtime/staff.v1.json'
import { runtimeConfigSchemaForAudience } from '@vmsh/contracts'

import { createStaffStatisticsClient } from './staff-statistics-client'

const runtime = runtimeConfigSchemaForAudience('staff').parse(runtimeFixture.response)

const emptyResponse = {
  schemaVersion: 1,
  courses: [],
  selectedCourseId: null,
  selectedGroupId: null,
  run: null,
  lessons: [],
  requestId: 'request-1',
}

describe('Staff statistics client', () => {
  it('sends validated course/group filters with credentials', async () => {
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValue(Response.json(emptyResponse))
    const client = createStaffStatisticsClient(runtime, { fetchImplementation })

    await client.get({ courseId: 'course.math', groupId: 'group.beginner' })

    expect(fetchImplementation).toHaveBeenCalledWith(
      '/staff/api/v1/statistics?courseId=course.math&groupId=group.beginner',
      expect.objectContaining({ method: 'GET', credentials: 'include', cache: 'no-store' }),
    )
  })

  it('uses the unfiltered endpoint when no selection exists', async () => {
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValue(Response.json(emptyResponse))
    const client = createStaffStatisticsClient(runtime, { fetchImplementation })
    await client.get({ courseId: null, groupId: null })
    expect(fetchImplementation.mock.calls[0]?.[0]).toBe('/staff/api/v1/statistics')
  })
})

it('retries an expired admin session with the same calculation key', async () => {
  const { createStatisticsRecalculationClient } = await import('./staff-statistics-client')
  const refresh = vi.fn().mockResolvedValue(undefined)
  const request = vi
    .fn<typeof fetch>()
    .mockResolvedValueOnce(new Response('', { status: 401 }))
    .mockResolvedValueOnce(Response.json({ busy: true, operation: null }))
  vi.stubGlobal('fetch', request)
  try {
    const client = createStatisticsRecalculationClient(runtime, refresh)
    expect(await client('c-1', 'request-1')).toEqual({ busy: true, operation: null })
    expect(refresh).toHaveBeenCalledOnce()
    expect(request).toHaveBeenCalledTimes(2)
    expect(request.mock.calls[0]).toEqual(request.mock.calls[1])
    expect(request.mock.calls[0]?.[1]).toMatchObject({
      credentials: 'include',
      method: 'POST',
      cache: 'no-store',
      body: JSON.stringify({ courseId: 'c-1', idempotencyKey: 'request-1' }),
    })
  } finally {
    vi.unstubAllGlobals()
  }
})
