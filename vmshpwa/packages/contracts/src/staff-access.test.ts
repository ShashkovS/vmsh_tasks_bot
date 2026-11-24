import { describe, expect, it } from 'vitest'

import {
  createStaffMemberBatchRequestSchema,
  createStaffMemberBatchResponseSchema,
  replaceStaffScopesRequestSchema,
  staffAccessDirectoryResponseSchema,
  staffAccessQueryKey,
} from './staff-access'

const scope = {
  courseId: 'course-math',
  courseCode: 'math-57',
  courseName: 'Математика 5–7',
  courseStatus: 'active' as const,
  groupId: 'group-beginner',
  groupCode: 'н',
  groupName: 'Начинающие',
  groupStatus: 'active' as const,
  version: 1,
}

describe('Staff access contract', () => {
  it('accepts the exact directory shape', () => {
    const parsed = staffAccessDirectoryResponseSchema.parse({
      schemaVersion: 1,
      members: [
        {
          staffUserId: 'teacher-one',
          name: 'Мария',
          surname: 'Учитель',
          middleName: null,
          role: 'teacher',
          account: {
            accountId: 'account-teacher',
            username: 'teacher',
            status: 'active',
          },
          scopes: [scope],
        },
      ],
      requestId: 'staff-access-test',
    })

    expect(parsed.members[0]?.scopes[0]?.groupName).toBe('Начинающие')
    expect(staffAccessQueryKey({ audience: 'staff', accountId: 'account-admin' })).toEqual([
      'staff-access',
      'principal',
      'staff',
      'account-admin',
    ])
  })

  it('rejects duplicated and redundant desired scopes', () => {
    const base = {
      schemaVersion: 1 as const,
      expectedScopes: [],
    }
    expect(() =>
      replaceStaffScopesRequestSchema.parse({
        ...base,
        scopes: [
          { courseId: 'course-math', groupId: 'group-beginner' },
          { courseId: 'course-math', groupId: 'group-beginner' },
        ],
      }),
    ).toThrow()
    expect(() =>
      replaceStaffScopesRequestSchema.parse({
        ...base,
        scopes: [
          { courseId: 'course-math', groupId: null },
          { courseId: 'course-math', groupId: 'group-beginner' },
        ],
      }),
    ).toThrow()
  })

  it('validates an atomic teacher batch without returning passwords', () => {
    const request = createStaffMemberBatchRequestSchema.parse({
      schemaVersion: 1,
      rows: [
        {
          surname: 'Учитель',
          name: 'Мария',
          middleName: null,
          username: 'teacher-batch',
          password: 'temporary-password',
        },
      ],
      scopes: [{ courseId: 'course-math', groupId: null }],
    })
    expect(request.rows).toHaveLength(1)

    const response = createStaffMemberBatchResponseSchema.parse({
      schemaVersion: 1,
      counts: { total: 1, created: 1 },
      requestId: 'teacher-batch-request',
    })
    expect(response).not.toHaveProperty('rows')
    expect(JSON.stringify(response)).not.toContain('password')
  })
})
