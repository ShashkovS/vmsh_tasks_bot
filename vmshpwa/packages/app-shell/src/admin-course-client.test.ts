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

  it('loads the Student directory and sends one complete enrollment update', async () => {
    const enrollment = {
      enrollmentId: 'enrollment-student',
      course: {
        courseId: 'course-math',
        code: 'math-57',
        name: 'Математика 5–7',
        subjectCode: 'math',
      },
      activeGroupId: 'group-beginner',
      allowedGroups: [
        {
          groupId: 'group-beginner',
          code: 'н',
          name: 'Начинающие',
          status: 'active' as const,
          colorKey: 'level-1',
          sortOrder: 1,
        },
      ],
      attendanceMode: 'online' as const,
      status: 'active' as const,
      version: 1,
    }
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        Response.json({
          schemaVersion: 1,
          students: [
            {
              studentId: 'student-one',
              surname: 'Иванов',
              name: 'Иван',
              middleName: null,
              grade: 6,
              birthday: null,
              strength: null,
              webAccount: null,
              familyAccounts: [],
              enrollments: [enrollment],
            },
          ],
          requestId: 'directory',
        }),
      )
      .mockResolvedValueOnce(Response.json({ schemaVersion: 1, enrollment, requestId: 'updated' }))
    const client = createAdminCourseClient(runtime, { fetchImplementation })

    await client.listStudentEnrollments()
    await client.updateStudentEnrollment(enrollment.enrollmentId, 1, {
      schemaVersion: 1,
      activeGroupId: enrollment.activeGroupId,
      allowedGroupIds: [enrollment.activeGroupId],
      attendanceMode: enrollment.attendanceMode,
      status: enrollment.status,
    })

    expect(fetchImplementation.mock.calls[0]?.[0]).toBe('/staff/api/v1/student-enrollments')
    expect(fetchImplementation.mock.calls[1]?.[0]).toBe(
      '/staff/api/v1/course-enrollments/enrollment-student',
    )
    expect(fetchImplementation.mock.calls[1]?.[1]?.headers).toEqual(
      expect.objectContaining({ 'If-Match': '"enrollment-student:v1"' }),
    )
  })

  it('loads Staff access and replaces the complete optimistic scope set', async () => {
    const member = {
      staffUserId: 'teacher-one',
      name: 'Мария',
      surname: 'Учитель',
      middleName: null,
      role: 'teacher' as const,
      account: null,
      scopes: [
        {
          courseId: 'course-math',
          courseCode: 'math-57',
          courseName: 'Математика 5–7',
          courseStatus: 'active' as const,
          groupId: 'group-beginner',
          groupCode: 'н',
          groupName: 'Начинающие',
          groupStatus: 'active' as const,
          version: 2,
        },
      ],
    }
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        Response.json({ schemaVersion: 1, members: [member], requestId: 'list' }),
      )
      .mockResolvedValueOnce(Response.json({ schemaVersion: 1, member, requestId: 'replace' }))
    const client = createAdminCourseClient(runtime, { fetchImplementation })

    await client.listStaffAccess()
    await client.replaceStaffScopes(member.staffUserId, {
      schemaVersion: 1,
      expectedScopes: member.scopes.map(({ courseId, groupId, version }) => ({
        courseId,
        groupId,
        version,
      })),
      scopes: [{ courseId: 'course-math', groupId: null }],
    })

    expect(fetchImplementation.mock.calls[0]?.[0]).toBe('/staff/api/v1/staff-access')
    expect(fetchImplementation.mock.calls[1]?.[0]).toBe(
      '/staff/api/v1/staff-members/teacher-one/scopes',
    )
    expect(fetchImplementation.mock.calls[1]?.[1]?.body).toContain('"groupId":null')
  })

  it('uploads a problem workbook without overriding the multipart boundary', async () => {
    const response = {
      schemaVersion: 1,
      course: { courseId: 'course-math', code: 'math', name: 'Математика' },
      source: { filename: 'tasks.xlsx', sha256: 'a'.repeat(64) },
      previewSha256: 'b'.repeat(64),
      summary: { rows: 0, create: 0, update: 0, unchanged: 0, invalid: 0 },
      rows: [],
      requestId: 'preview',
    }
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(Response.json(response))
    const client = createAdminCourseClient(runtime, { fetchImplementation })
    const workbook = new File(['xlsx'], 'tasks.xlsx')

    await expect(client.previewProblemImport('course-math', workbook)).resolves.toEqual(response)

    const [url, init] = fetchImplementation.mock.calls[0]!
    expect(url).toBe('/staff/api/v1/problem-imports/preview')
    expect(init?.headers).toEqual({ Accept: 'application/json' })
    expect(init?.body).toBeInstanceOf(FormData)
    expect((init?.body as FormData).get('courseId')).toBe('course-math')
    expect(((init?.body as FormData).get('workbook') as File).name).toBe('tasks.xlsx')
  })

  it('applies the reviewed workbook and rolls its receipt back', async () => {
    const applied = {
      schemaVersion: 1,
      importId: 'problem-import.one',
      state: 'applied' as const,
      source: { filename: 'tasks.xlsx', sha256: 'a'.repeat(64) },
      previewSha256: 'b'.repeat(64),
      summary: { rows: 2, created: 1, updated: 1, unchanged: 0, skippedInvalid: 0 },
      appliedAt: '2026-07-30T10:00:00+00:00',
      rolledBackAt: null,
      version: 1,
      replayed: false,
      requestId: 'apply',
    }
    const rolledBack = {
      ...applied,
      state: 'rolled_back' as const,
      rolledBackAt: '2026-07-30T10:05:00+00:00',
      version: 2,
      requestId: 'rollback',
    }
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(Response.json(applied))
      .mockResolvedValueOnce(Response.json(rolledBack))
    const client = createAdminCourseClient(runtime, { fetchImplementation })
    const workbook = new File(['xlsx'], 'tasks.xlsx')

    await expect(
      client.applyProblemImport('course-math', workbook, 'a'.repeat(64), 'b'.repeat(64)),
    ).resolves.toEqual(applied)
    await expect(client.rollbackProblemImport(applied.importId, applied.version)).resolves.toEqual(
      rolledBack,
    )

    const applyBody = fetchImplementation.mock.calls[0]?.[1]?.body as FormData
    expect(applyBody.get('sourceSha256')).toBe('a'.repeat(64))
    expect(applyBody.get('previewSha256')).toBe('b'.repeat(64))
    expect(fetchImplementation.mock.calls[1]?.[0]).toBe(
      '/staff/api/v1/problem-imports/problem-import.one/rollback',
    )
    expect(fetchImplementation.mock.calls[1]?.[1]?.body).toBe('{"expectedVersion":1}')
  })
})
