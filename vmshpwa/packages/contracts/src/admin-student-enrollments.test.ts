import directoryFixture from '@vmsh/contracts/fixtures/admin-enrollments/directory.v1.json'
import { describe, expect, it } from 'vitest'

import {
  adminStudentEnrollmentDirectoryResponseSchema,
  adminStudentEnrollmentsQueryKey,
  createFamilyAccountRequestSchema,
  familyAccountLinkResponseSchema,
  linkFamilyAccountRequestSchema,
  managedAccountResponseSchema,
  replaceManagedAccountCredentialRequestSchema,
  updateManagedAccountStatusRequestSchema,
  updateAdminStudentEnrollmentRequestSchema,
  unlinkFamilyAccountResponseSchema,
} from './admin-student-enrollments'

describe('admin student enrollment contracts', () => {
  it('accepts the committed Staff directory fixture', () => {
    const directory = adminStudentEnrollmentDirectoryResponseSchema.parse(directoryFixture)
    expect(directory.students[0]?.enrollments[0]?.activeGroupId).toBe('group-fixture-beginner')
    expect(directory.students[0]?.webAccount?.credentialVersion).toBe(1)
    expect(directory.students[0]?.familyAccounts[0]?.username).toBe('family-testovye')
  })

  it('keeps Family passwords write-only while validating create, link and unlink payloads', () => {
    const created = createFamilyAccountRequestSchema.parse({
      schemaVersion: 1,
      username: ' family-login ',
      displayName: ' Семья Ивановых ',
      password: 'family-password',
      relationshipLabel: ' родитель ',
      isPrimary: true,
    })
    expect(created).toEqual({
      schemaVersion: 1,
      username: 'family-login',
      displayName: 'Семья Ивановых',
      password: 'family-password',
      relationshipLabel: 'родитель',
      isPrimary: true,
    })
    expect(
      linkFamilyAccountRequestSchema.parse({
        schemaVersion: 1,
        familyUsername: ' family-login ',
        relationshipLabel: ' родитель ',
        isPrimary: false,
      }).familyUsername,
    ).toBe('family-login')

    const response = familyAccountLinkResponseSchema.parse({
      schemaVersion: 1,
      account: {
        accountId: 'family-account-one',
        username: 'family-login',
        displayName: 'Семья Ивановых',
        status: 'active',
        credentialVersion: 1,
      },
      link: {
        studentId: 'student-one',
        relationshipLabel: 'родитель',
        isPrimary: true,
      },
      requestId: 'request-family-create',
    })
    expect(response).not.toHaveProperty('password')
    expect(response.account).not.toHaveProperty('password')
    expect(
      unlinkFamilyAccountResponseSchema.parse({
        schemaVersion: 1,
        studentId: 'student-one',
        accountId: 'family-account-one',
        revoked: true,
        requestId: 'request-family-unlink',
      }).revoked,
    ).toBe(true)
  })

  it('validates account lifecycle commands and responses', () => {
    expect(
      updateManagedAccountStatusRequestSchema.parse({ schemaVersion: 1, status: 'blocked' }),
    ).toEqual({ schemaVersion: 1, status: 'blocked' })
    expect(
      replaceManagedAccountCredentialRequestSchema.parse({
        schemaVersion: 1,
        credential: 'replacement-token',
      }).credential,
    ).toBe('replacement-token')
    expect(
      managedAccountResponseSchema.parse({
        schemaVersion: 1,
        account: {
          accountId: 'account-student',
          audience: 'student',
          status: 'active',
          credentialVersion: 2,
        },
        requestId: 'request-account',
      }).account.credentialVersion,
    ).toBe(2)
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
