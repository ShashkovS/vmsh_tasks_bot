import runtimeFixture from '@vmsh/contracts/fixtures/runtime/staff.v1.json'
import { runtimeConfigSchemaForAudience } from '@vmsh/contracts'
import { describe, expect, it, vi } from 'vitest'

import { createAdminCourseClient } from './admin-course-client'

const runtime = runtimeConfigSchemaForAudience('staff').parse(runtimeFixture.response)
const group = {
  groupId: 'group-beginner',
  shortCode: 'н',
  name: 'Начинающие',
  status: 'active' as const,
  colorKey: 'beginner',
  sortOrder: 1,
  allowSelfSwitch: false,
  isDefault: false,
  isSystem: false,
  scoreWeight: 1,
  activeStudents: 10,
  version: 1,
}
const course = {
  courseId: 'course-math',
  code: 'math-57',
  name: 'Математика 5–7',
  subjectCode: 'math',
  status: 'active' as const,
  sortOrder: 1,
  accentKey: 'math',
  activeStudents: 10,
  groups: [group],
  version: 1,
}

describe('admin course client', () => {
  it('loads and validates the real Staff catalog', async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(
      Response.json({
        schemaVersion: 1,
        season: {
          seasonId: 'season-2026',
          code: '2026',
          title: '2026–2027',
          status: 'active',
        },
        courses: [course],
        requestId: 'catalog-request',
      }),
    )
    const result = await createAdminCourseClient(runtime, { fetchImplementation }).list()
    expect(result.courses[0]?.groups[0]?.shortCode).toBe('н')
    expect(fetchImplementation.mock.calls[0]?.[0]).toBe('/staff/api/v1/courses')
  })

  it('normalizes a create request and sends exact optimistic ETags', async () => {
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        Response.json({ schemaVersion: 1, course: { ...course, groups: [] }, requestId: 'create' }),
      )
      .mockResolvedValueOnce(
        Response.json({ schemaVersion: 1, course: { ...course, version: 2 }, requestId: 'edit' }),
      )
      .mockResolvedValueOnce(Response.json({ schemaVersion: 1, group, requestId: 'group' }))
    const client = createAdminCourseClient(runtime, { fetchImplementation })
    await client.createCourse({
      schemaVersion: 1,
      seasonId: 'season-2026',
      code: ' MATH-57 ',
      name: 'Математика 5–7',
      subjectCode: ' MATH ',
      status: 'active',
      sortOrder: 1,
      accentKey: 'math',
    })
    await client.updateCourse(course.courseId, 1, {
      schemaVersion: 1,
      code: course.code,
      name: course.name,
      subjectCode: course.subjectCode,
      status: course.status,
      sortOrder: course.sortOrder,
      accentKey: course.accentKey,
    })
    await client.updateGroup(group.groupId, 1, {
      schemaVersion: 1,
      shortCode: group.shortCode,
      name: group.name,
      status: group.status,
      colorKey: group.colorKey,
      sortOrder: group.sortOrder,
      allowSelfSwitch: group.allowSelfSwitch,
      scoreWeight: group.scoreWeight,
    })

    expect(fetchImplementation.mock.calls[0]?.[1]?.body).toContain('"code":"math-57"')
    expect(fetchImplementation.mock.calls[1]?.[1]?.headers).toEqual(
      expect.objectContaining({ 'If-Match': '"course-math:v1"' }),
    )
    expect(fetchImplementation.mock.calls[2]?.[1]?.headers).toEqual(
      expect.objectContaining({ 'If-Match': '"group-beginner:v1"' }),
    )
  })

  it('creates and confirms versioned course schedule drafts', async () => {
    const rule = {
      ruleId: 'schedule-rule.1',
      field: 'opens_at' as const,
      ruleVersion: 1,
      dayOffset: 0,
      localTime: '16:30:00',
      timezone: 'Europe/Moscow',
      state: 'draft' as const,
      version: 1,
    }
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        Response.json({
          schemaVersion: 1,
          rule,
          impact: { groupLessons: 3, materializedWindows: 1 },
          requestId: 'draft',
        }),
      )
      .mockResolvedValueOnce(
        Response.json({
          schemaVersion: 1,
          rule: { ...rule, state: 'active', version: 2 },
          requestId: 'confirm',
        }),
      )
    const client = createAdminCourseClient(runtime, { fetchImplementation })
    await client.createCourseScheduleDraft('course-math', {
      schemaVersion: 1,
      field: 'opens_at',
      dayOffset: 0,
      localTime: '16:30',
      timezone: 'Europe/Moscow',
    })
    await client.confirmCourseScheduleRule(rule.ruleId, rule.version)

    expect(fetchImplementation.mock.calls[0]?.[0]).toBe(
      '/staff/api/v1/courses/course-math/schedule-rules',
    )
    expect(fetchImplementation.mock.calls[1]?.[1]?.headers).toEqual(
      expect.objectContaining({ 'If-Match': '"schedule-rule.1:v1"' }),
    )
  })
})
