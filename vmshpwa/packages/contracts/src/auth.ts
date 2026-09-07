import { z } from 'zod'

/**
 * Phase-1 authentication contracts shared by the three browser audiences.
 * See `dev/development-plan/05-phase-1-auth.md` and
 * `docs/authentication-and-security.md`; fixture parity lives in
 * `src/auth.test.ts` and `fixtures/auth/*.v1.json`.
 */

export const audienceSchema = z.enum(['student', 'family', 'staff'])
export type Audience = z.infer<typeof audienceSchema>

export const publicIdSchema = z
  .string()
  .min(1)
  .max(128)
  .regex(
    /^[a-z0-9](?:[a-z0-9._:-]{0,126}[a-z0-9])?$/,
    'Public IDs must be canonical lowercase opaque identifiers',
  )
export type PublicId = z.infer<typeof publicIdSchema>

export const sessionPublicIdSchema = z
  .string()
  .regex(/^[0-9a-f]{32}$/, 'Session public ID must be exactly 32 lowercase hex digits')
  .brand<'SessionPublicId'>()
export type SessionPublicId = z.infer<typeof sessionPublicIdSchema>

export const canonicalTokenSchema = z
  .string()
  .min(1)
  .max(64)
  .regex(/^[a-z][a-z0-9._:-]*$/, 'Token must use canonical lowercase ASCII')

const usernameSchema = z.string().trim().min(1).max(128)
const credentialSchema = z.string().min(1).max(512)
const deviceLabelInputSchema = z.string().trim().min(1).max(120)
const displayNameSchema = z.string().trim().min(1).max(200)
const versionSchema = z.number().int().positive()

export const studentLoginRequestSchema = z
  .object({
    username: usernameSchema,
    telegramToken: credentialSchema,
    deviceLabel: deviceLabelInputSchema.optional(),
  })
  .strict()
export type StudentLoginRequest = z.infer<typeof studentLoginRequestSchema>

const passwordLoginRequestShape = {
  username: usernameSchema,
  password: credentialSchema,
  deviceLabel: deviceLabelInputSchema.optional(),
}

export const familyLoginRequestSchema = z.object(passwordLoginRequestShape).strict()
export type FamilyLoginRequest = z.infer<typeof familyLoginRequestSchema>

export const staffLoginRequestSchema = z.object(passwordLoginRequestShape).strict()
export type StaffLoginRequest = z.infer<typeof staffLoginRequestSchema>

export const familyLinkedChildSummarySchema = z
  .object({
    studentId: publicIdSchema,
    displayName: displayNameSchema,
    relationshipLabel: z.string().trim().min(1).max(80).nullable(),
    isPrimary: z.boolean(),
  })
  .strip()
export type FamilyLinkedChildSummary = z.infer<typeof familyLinkedChildSummarySchema>

export const staffRoleSchema = z.enum(['teacher', 'admin'])
export type StaffRole = z.infer<typeof staffRoleSchema>

// Exact wire registry from `helpers/pwa/permissions.py::Capability`. Object
// scope remains a separate backend check; unknown tokens fail closed here.
export const STAFF_CAPABILITY_VALUES = [
  'account.sessions.manage',
  'self.read',
  'course.read',
  'group.read',
  'own-work.read',
  'submission.manage',
  'thread.manage',
  'progress.read',
  'news.read',
  'notification.manage',
  'family-child.read',
  'student.read',
  'review.read',
  'review.write',
  'oral.manage',
  'student.active-group.write',
  'statistics.read',
  'product-analytics.read',
  'course.manage',
  'group.manage',
  'content.manage',
  'checker.manage',
  'broadcast.manage',
  'classroom.manage',
  'audit.read',
  'staff.manage',
  'telegram-binding.manage',
] as const

export const staffCapabilitySchema = z.enum(STAFF_CAPABILITY_VALUES)
export type StaffCapability = z.infer<typeof staffCapabilitySchema>

export const staffScopeSchema = z
  .object({
    courseId: publicIdSchema,
    groupId: publicIdSchema.nullable(),
    role: staffRoleSchema,
    validFrom: z.iso.datetime(),
    validTo: z.iso.datetime().nullable(),
    version: versionSchema,
  })
  .strip()
export type StaffScope = z.infer<typeof staffScopeSchema>

const principalCommonShape = {
  accountId: publicIdSchema,
  displayName: displayNameSchema,
  sessionVersion: versionSchema,
  credentialVersion: versionSchema,
}

export const studentPrincipalSchema = z
  .object({
    ...principalCommonShape,
    audience: z.literal('student'),
    userId: publicIdSchema,
  })
  .strip()
export type StudentPrincipal = z.infer<typeof studentPrincipalSchema>

export const familyPrincipalSchema = z
  .object({
    ...principalCommonShape,
    audience: z.literal('family'),
    linkedChildren: z.array(familyLinkedChildSummarySchema),
  })
  .strip()
export type FamilyPrincipal = z.infer<typeof familyPrincipalSchema>

export const staffPrincipalSchema = z
  .object({
    ...principalCommonShape,
    audience: z.literal('staff'),
    userId: publicIdSchema,
    role: staffRoleSchema,
    capabilities: z.array(staffCapabilitySchema),
    scopes: z.array(staffScopeSchema),
  })
  .strip()
export type StaffPrincipal = z.infer<typeof staffPrincipalSchema>

export const principalSchema = z.discriminatedUnion('audience', [
  studentPrincipalSchema,
  familyPrincipalSchema,
  staffPrincipalSchema,
])
export type Principal = z.infer<typeof principalSchema>

export const authSessionSummarySchema = z
  .object({
    sessionId: sessionPublicIdSchema,
    audience: audienceSchema,
    isCurrent: z.boolean(),
    deviceLabel: z.string().trim().min(1).max(120).nullable(),
    userAgentFamily: z.string().trim().min(1).max(120).nullable(),
    createdAt: z.iso.datetime(),
    lastSeenAt: z.iso.datetime(),
    expiresAt: z.iso.datetime(),
  })
  .strip()
export type AuthSessionSummary = z.infer<typeof authSessionSummarySchema>

export const authPolicySchema = z
  .object({
    accessExpiresAt: z.iso.datetime(),
    sessionExpiresAt: z.iso.datetime(),
    supportEmail: z.string().email(),
  })
  .strip()
export type AuthPolicy = z.infer<typeof authPolicySchema>

export const authContextSchema = z
  .object({
    principal: principalSchema,
    currentSession: authSessionSummarySchema.extend({ isCurrent: z.literal(true) }),
    policy: authPolicySchema,
  })
  .strip()
  .superRefine((contextValue, refinementContext) => {
    if (contextValue.currentSession.audience !== contextValue.principal.audience) {
      refinementContext.addIssue({
        code: 'custom',
        message: 'Current session audience must match principal audience',
        path: ['currentSession', 'audience'],
      })
    }
    if (contextValue.currentSession.expiresAt !== contextValue.policy.sessionExpiresAt) {
      refinementContext.addIssue({
        code: 'custom',
        message: 'Current session expiry must match the server session policy',
        path: ['policy', 'sessionExpiresAt'],
      })
    }
  })
export type AuthContext = z.infer<typeof authContextSchema>

export const authSessionsResponseSchema = z
  .object({
    audience: audienceSchema,
    sessions: z.array(authSessionSummarySchema).min(1),
  })
  .strip()
  .superRefine((response, context) => {
    const currentSessions = response.sessions.filter((session) => session.isCurrent)
    if (currentSessions.length !== 1) {
      context.addIssue({
        code: 'custom',
        message: 'An authenticated session list must contain exactly one current session',
        path: ['sessions'],
      })
    }

    const seenSessionIds = new Set<string>()
    response.sessions.forEach((session, index) => {
      if (session.audience !== response.audience) {
        context.addIssue({
          code: 'custom',
          message: 'Session audience must match response audience',
          path: ['sessions', index, 'audience'],
        })
      }
      if (seenSessionIds.has(session.sessionId)) {
        context.addIssue({
          code: 'custom',
          message: 'Session IDs must be unique',
          path: ['sessions', index, 'sessionId'],
        })
      }
      seenSessionIds.add(session.sessionId)
    })
  })
export type AuthSessionsResponse = z.infer<typeof authSessionsResponseSchema>

export const PRE_AUTH_ERROR_CODES = [
  'invalid_credentials',
  'account_unavailable',
  'rate_limited',
] as const

export const AUTH_ERROR_CODES = [
  ...PRE_AUTH_ERROR_CODES,
  'authentication_required',
  'session_expired',
  'session_revoked',
  'forbidden',
] as const

export const preAuthErrorCodeSchema = z.enum(PRE_AUTH_ERROR_CODES)
export type PreAuthErrorCode = z.infer<typeof preAuthErrorCodeSchema>
export const authErrorCodeSchema = z.enum(AUTH_ERROR_CODES)
export type AuthErrorCode = z.infer<typeof authErrorCodeSchema>

export interface PrincipalQueryScope {
  audience: Audience
  accountId: string
}

export function principalQueryKey(principal: PrincipalQueryScope) {
  const audience = audienceSchema.parse(principal.audience)
  const accountId = publicIdSchema.parse(principal.accountId)
  return ['principal', audience, accountId] as const
}

export const authQueryKeys = {
  all: (audience: Audience) => ['auth', audienceSchema.parse(audience)] as const,
  me: (audience: Audience) => [...authQueryKeys.all(audience), 'me'] as const,
  principal: (principal: PrincipalQueryScope) => principalQueryKey(principal),
  sessions: (principal: PrincipalQueryScope) =>
    [...principalQueryKey(principal), 'sessions'] as const,
} as const

export const AUTH_CONTRACT_FIXTURE_VERSION = 1 as const
const authContractFixtureVersionSchema = z.literal(AUTH_CONTRACT_FIXTURE_VERSION)

const authContractFixtureBaseShape = {
  fixtureVersion: authContractFixtureVersionSchema,
  authContext: authContextSchema,
  sessionsResponse: authSessionsResponseSchema,
}

export const authContractFixtureSchema = z
  .discriminatedUnion('audience', [
    z
      .object({
        ...authContractFixtureBaseShape,
        audience: z.literal('student'),
        loginRequest: studentLoginRequestSchema,
      })
      .strict(),
    z
      .object({
        ...authContractFixtureBaseShape,
        audience: z.literal('family'),
        loginRequest: familyLoginRequestSchema,
      })
      .strict(),
    z
      .object({
        ...authContractFixtureBaseShape,
        audience: z.literal('staff'),
        loginRequest: staffLoginRequestSchema,
      })
      .strict(),
  ])
  .superRefine((fixture, context) => {
    if (fixture.authContext.principal.audience !== fixture.audience) {
      context.addIssue({
        code: 'custom',
        message: 'Fixture principal audience must match fixture audience',
        path: ['authContext', 'principal', 'audience'],
      })
    }
    if (fixture.sessionsResponse.audience !== fixture.audience) {
      context.addIssue({
        code: 'custom',
        message: 'Fixture session-list audience must match fixture audience',
        path: ['sessionsResponse', 'audience'],
      })
    }
  })
export type AuthContractFixture = z.infer<typeof authContractFixtureSchema>

export const authInvalidFixtureTargetSchema = z.enum([
  'student_login_request',
  'family_login_request',
  'staff_login_request',
  'principal',
  'auth_context',
  'sessions_response',
  'session_public_id',
  'auth_error_code',
])
export type AuthInvalidFixtureTarget = z.infer<typeof authInvalidFixtureTargetSchema>

export const authInvalidContractFixtureSchema = z
  .object({
    fixtureVersion: authContractFixtureVersionSchema,
    cases: z
      .array(
        z
          .object({
            name: canonicalTokenSchema,
            target: authInvalidFixtureTargetSchema,
            payload: z.unknown(),
          })
          .strict(),
      )
      .min(1),
  })
  .strict()
export type AuthInvalidContractFixture = z.infer<typeof authInvalidContractFixtureSchema>
