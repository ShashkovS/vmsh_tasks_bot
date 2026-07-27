import type { ZodType } from 'zod'
import { describe, expect, it } from 'vitest'

import familyFixture from '../fixtures/auth/family.v1.json'
import invalidAuthFixture from '../fixtures/auth/invalid.v1.json'
import staffFixture from '../fixtures/auth/staff.v1.json'
import studentFixture from '../fixtures/auth/student.v1.json'

import {
  AUTH_ERROR_CODES,
  PRE_AUTH_ERROR_CODES,
  authContextSchema,
  authContractFixtureSchema,
  authErrorCodeSchema,
  authInvalidContractFixtureSchema,
  authQueryKeys,
  authSessionsResponseSchema,
  familyLoginRequestSchema,
  principalSchema,
  staffLoginRequestSchema,
  studentLoginRequestSchema,
  type AuthInvalidFixtureTarget,
} from './auth'

const validFixtures: unknown[] = [studentFixture, familyFixture, staffFixture]

const invalidTargetSchemas: Record<AuthInvalidFixtureTarget, ZodType> = {
  student_login_request: studentLoginRequestSchema,
  family_login_request: familyLoginRequestSchema,
  staff_login_request: staffLoginRequestSchema,
  principal: principalSchema,
  auth_context: authContextSchema,
  sessions_response: authSessionsResponseSchema,
  auth_error_code: authErrorCodeSchema,
}

describe('Phase-1 authentication contracts', () => {
  it('keeps all audience fixtures in parity with the versioned contract', () => {
    for (const fixture of validFixtures) {
      expect(authContractFixtureSchema.parse(fixture)).toEqual(fixture)
    }
  })

  it('expresses the 10 August Moscow session boundary as the correct UTC instant', () => {
    for (const fixture of validFixtures) {
      const parsed = authContractFixtureSchema.parse(fixture)
      expect(parsed.authContext.policy.sessionExpiresAt).toBe('2026-08-09T21:00:00Z')
      expect(parsed.authContext.currentSession.expiresAt).toBe('2026-08-09T21:00:00Z')
    }
  })

  it('uses an audience-specific credential field without a body audience', () => {
    const student = authContractFixtureSchema.parse(studentFixture)
    const family = authContractFixtureSchema.parse(familyFixture)
    const staff = authContractFixtureSchema.parse(staffFixture)

    expect(student.audience).toBe('student')
    if (student.audience !== 'student') throw new Error('Expected student fixture')
    expect(student.loginRequest.telegramToken).toBe('synthetic-telegram-token-not-a-secret')
    expect(student.loginRequest).not.toHaveProperty('audience')

    expect(family.audience).toBe('family')
    if (family.audience !== 'family') throw new Error('Expected family fixture')
    expect(family.loginRequest.password).toBe('synthetic-family-password-not-a-secret')
    expect(family.loginRequest).not.toHaveProperty('audience')

    expect(staff.audience).toBe('staff')
    if (staff.audience !== 'staff') throw new Error('Expected staff fixture')
    expect(staff.loginRequest.password).toBe('synthetic-staff-password-not-a-secret')
    expect(staff.loginRequest).not.toHaveProperty('audience')
  })

  it('discriminates principals and exposes only public family/staff scope summaries', () => {
    const familyContext = authContextSchema.parse(familyFixture.authContext)
    expect(familyContext.principal.audience).toBe('family')
    if (familyContext.principal.audience !== 'family') throw new Error('Expected family principal')
    expect(familyContext.principal.linkedChildren).toHaveLength(2)
    expect(familyContext.principal.linkedChildren[0]?.studentId).toBe('user-child-alpha')

    const staffContext = authContextSchema.parse(staffFixture.authContext)
    expect(staffContext.principal.audience).toBe('staff')
    if (staffContext.principal.audience !== 'staff') throw new Error('Expected staff principal')
    expect(staffContext.principal.role).toBe('teacher')
    expect(staffContext.principal.capabilities).toContain('review')
    expect(staffContext.principal.scopes).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ courseId: 'course-fixture-alpha', groupId: null }),
        expect.objectContaining({
          courseId: 'course-fixture-beta',
          groupId: 'group-fixture-beta-one',
        }),
      ]),
    )
  })

  it('rejects every versioned invalid fixture case', () => {
    const fixture = authInvalidContractFixtureSchema.parse(invalidAuthFixture)
    for (const invalidCase of fixture.cases) {
      expect(
        invalidTargetSchemas[invalidCase.target].safeParse(invalidCase.payload).success,
        invalidCase.name,
      ).toBe(false)
    }
  })

  it('keeps pre-auth errors generic and stable', () => {
    expect(PRE_AUTH_ERROR_CODES).toEqual([
      'invalid_credentials',
      'account_unavailable',
      'rate_limited',
    ])
    expect(AUTH_ERROR_CODES).toContain('session_revoked')
    expect(authErrorCodeSchema.safeParse('blocked').success).toBe(false)
    expect(authErrorCodeSchema.safeParse('disabled').success).toBe(false)
  })

  it('requires exactly one current, audience-matching session', () => {
    const sessions = authSessionsResponseSchema.parse(studentFixture.sessionsResponse)
    expect(sessions.sessions.filter((session) => session.isCurrent)).toHaveLength(1)

    expect(() =>
      authSessionsResponseSchema.parse({
        ...sessions,
        sessions: sessions.sessions.map((session) => ({ ...session, isCurrent: true })),
      }),
    ).toThrow()
    expect(() =>
      authSessionsResponseSchema.parse({
        ...sessions,
        sessions: [{ ...sessions.sessions[0], audience: 'family' }],
      }),
    ).toThrow()
  })

  it('isolates principal-scoped query keys by audience and account', () => {
    const student = authContextSchema.parse(studentFixture.authContext).principal
    const otherStudent = { ...student, accountId: 'account-student-other' }
    const family = authContextSchema.parse(familyFixture.authContext).principal

    expect(authQueryKeys.sessions(student)).toEqual([
      'principal',
      'student',
      'account-student-fixture',
      'sessions',
    ])
    expect(authQueryKeys.sessions(student)).not.toEqual(authQueryKeys.sessions(otherStudent))
    expect(authQueryKeys.sessions(student)).not.toEqual(authQueryKeys.sessions(family))
  })

  it('rejects unknown fixture versions', () => {
    expect(
      authContractFixtureSchema.safeParse({ ...studentFixture, fixtureVersion: 2 }).success,
    ).toBe(false)
    expect(
      authInvalidContractFixtureSchema.safeParse({
        ...invalidAuthFixture,
        fixtureVersion: 2,
      }).success,
    ).toBe(false)
  })
})
