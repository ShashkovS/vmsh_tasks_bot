import { describe, expect, it } from 'vitest'

import {
  adminCourseScheduleDraftResponseSchema,
  adminCourseScheduleQueryKey,
  saveAdminGroupScheduleOverrideSchema,
} from './admin-course-schedule'

describe('admin course schedule contracts', () => {
  it('accepts the strict draft and impact response', () => {
    const parsed = adminCourseScheduleDraftResponseSchema.parse({
      schemaVersion: 1,
      rule: {
        ruleId: 'schedule-rule.1',
        field: 'opens_at',
        ruleVersion: 1,
        dayOffset: 0,
        localTime: '16:30:00',
        timezone: 'Europe/Moscow',
        state: 'draft',
        version: 1,
      },
      impact: { groupLessons: 3, materializedWindows: 2 },
      requestId: 'schedule-contract',
    })
    expect(parsed.impact.materializedWindows).toBe(2)
  })

  it('keeps override values consistent with the selected mode', () => {
    expect(() =>
      saveAdminGroupScheduleOverrideSchema.parse({
        schemaVersion: 1,
        field: 'hint_scheduled_at',
        mode: 'inherit',
        dayOffset: 5,
        localTime: null,
        timezone: null,
      }),
    ).toThrow()
    expect(() =>
      saveAdminGroupScheduleOverrideSchema.parse({
        schemaVersion: 1,
        field: 'submission_closes_at',
        mode: 'disabled',
        dayOffset: null,
        localTime: null,
        timezone: null,
      }),
    ).toThrow()
  })

  it('scopes query keys by Staff account and course', () => {
    expect(
      adminCourseScheduleQueryKey({ audience: 'staff', accountId: 'account-admin' }, 'course-math'),
    ).toContain('course-math')
  })
})
