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
