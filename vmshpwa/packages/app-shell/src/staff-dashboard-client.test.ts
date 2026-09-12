import { describe, expect, it, vi } from 'vitest'

import runtimeFixture from '@vmsh/contracts/fixtures/runtime/staff.v1.json'
import { runtimeConfigSchemaForAudience } from '@vmsh/contracts'

import { createStaffDashboardClient } from './staff-dashboard-client'

const runtime = runtimeConfigSchemaForAudience('staff').parse(runtimeFixture.response)

describe('Staff dashboard client', () => {
  it('loads the no-store audience endpoint', async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          schemaVersion: 1,
          generatedAt: '2026-08-02T12:00:00Z',
          summary: {
            review: { totalCases: 0, claimedByOthers: 0 },
            questions: { awaitingStaff: 0, olderThanOneHour: 0 },
            publications: { conditionsPublished: 0, groupLessons: 0 },
            oral: { openWindows: 0, upcomingWindows: 0 },
            delivery: null,
          },
          lessons: [],
          requestId: 'dashboard-client',
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    )
    const result = await createStaffDashboardClient(runtime, { fetchImplementation }).get()
    expect(result.lessons).toEqual([])
    expect(fetchImplementation).toHaveBeenCalledWith(
      '/staff/api/v1/dashboard',
      expect.objectContaining({ cache: 'no-store', credentials: 'include' }),
    )
  })

  it('requests the complete lesson history for the lesson catalog', async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          schemaVersion: 1,
          generatedAt: '2026-08-02T12:00:00Z',
          summary: {
            review: { totalCases: 0, claimedByOthers: 0 },
            questions: { awaitingStaff: 0, olderThanOneHour: 0 },
            publications: { conditionsPublished: 0, groupLessons: 0 },
            oral: { openWindows: 0, upcomingWindows: 0 },
            delivery: null,
          },
          lessons: [],
          requestId: 'dashboard-client-all',
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    )

    await createStaffDashboardClient(runtime, { fetchImplementation }).get('all')

    expect(fetchImplementation).toHaveBeenCalledWith(
      '/staff/api/v1/dashboard?view=all',
      expect.objectContaining({ cache: 'no-store', credentials: 'include' }),
    )
  })
})
