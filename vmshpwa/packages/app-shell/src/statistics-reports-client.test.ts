import { expect, it, vi } from 'vitest'
import runtimeFixture from '@vmsh/contracts/fixtures/runtime/staff.v1.json'
import { runtimeConfigSchemaForAudience } from '@vmsh/contracts'
import { createStatisticsReportsClient } from './statistics-reports-client'

it('fetches only the requested report and retries expired sessions', async () => {
  const fetchImplementation = vi
    .fn<typeof fetch>()
    .mockResolvedValueOnce(new Response('', { status: 401 }))
    .mockResolvedValueOnce(
      Response.json({
        schemaVersion: 1,
        courses: [],
        selectedCourseId: null,
        selectedGroupId: null,
        requestId: 'test',
        lessons: [],
      }),
    )
  const refreshSession = vi.fn().mockResolvedValue(undefined)
  const client = createStatisticsReportsClient(
    runtimeConfigSchemaForAudience('staff').parse(runtimeFixture.response),
    { fetchImplementation, refreshSession },
  )
  await client('summary', { courseId: 'c-1', groupId: null, lessonNumber: 0 })
  expect(refreshSession).toHaveBeenCalledOnce()
  expect(fetchImplementation).toHaveBeenCalledTimes(2)
  expect(fetchImplementation.mock.calls[1]?.[0]).toBe(
    '/staff/api/v1/statistics/summary?courseId=c-1',
  )
  expect(fetchImplementation.mock.calls[1]?.[1]).toMatchObject({
    credentials: 'include',
    cache: 'no-store',
  })
})
