import directoryFixture from '@vmsh/contracts/fixtures/admin-enrollments/directory.v1.json'
import { describe, expect, it } from 'vitest'

import {
  adminStudentEnrollmentDirectoryResponseSchema,
  adminStudentEnrollmentsQueryKey,
  updateAdminStudentEnrollmentRequestSchema,
} from './admin-student-enrollments'

describe('admin student enrollment contracts', () => {
  it('accepts the committed Staff directory fixture', () => {
    const directory = adminStudentEnrollmentDirectoryResponseSchema.parse(directoryFixture)
    expect(directory.students[0]?.enrollments[0]?.activeGroupId).toBe('group-fixture-beginner')
  })

  it('requires the active group to remain in the allowed set', () => {
    expect(() =>
      updateAdminStudentEnrollmentRequestSchema.parse({
        schemaVersion: 1,
        activeGroupId: 'group-expert',
        allowedGroupIds: ['group-beginner'],
        attendanceMode: 'online',
        status: 'active',
      }),
    ).toThrow()
  })

  it('scopes the directory cache to the Staff account', () => {
    expect(
      adminStudentEnrollmentsQueryKey({ audience: 'staff', accountId: 'account-admin' }),
    ).toEqual(['admin-student-enrollments', 'principal', 'staff', 'account-admin'])
  })
})
