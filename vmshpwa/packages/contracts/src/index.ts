import { z } from 'zod'

import { audienceSchema, type Audience } from './auth'

export * from './auth'
export * from './admin-course-catalog'
export * from './admin-course-schedule'
export * from './admin-student-enrollments'
export * from './classrooms'
export * from './content'
export * from './content-api'
export * from './courses'
export * from './family-courses'
export * from './news'
export * from './group-banners'
export * from './notifications'
export * from './oral-windows'
export * from './oral-results'
export * from './progress'
export * from './review-queue'
export * from './review-reactions'
export * from './submissions'
export * from './staff-access'
export * from './support'
export * from './telegram-bindings'
export * from './written-submissions'

export const runtimeContractVersionSchema = z.literal(1)
export const RUNTIME_CONTRACT_VERSION = runtimeContractVersionSchema.value
// Browser data migrations are independent from wire/fixture contract changes.
export const BROWSER_STORAGE_NAMESPACE_VERSION = 1 as const

export const runtimeInstanceSchema = z
  .string()
  .min(1)
  .max(64)
  .regex(
    /^[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?$/,
    'Runtime instance must be a canonical lowercase ASCII namespace token',
  )
export type RuntimeInstance = z.infer<typeof runtimeInstanceSchema>

export const runtimeBoundaryByAudience = {
  student: {
    appBase: '/student',
    apiBase: '/student/api/v1',
    websocketPath: '/student/ws',
  },
  family: {
    appBase: '/family',
    apiBase: '/family/api/v1',
    websocketPath: '/family/ws',
  },
  staff: {
    appBase: '/staff',
    apiBase: '/staff/api/v1',
    websocketPath: '/staff/ws',
  },
} as const satisfies Record<Audience, RuntimeBoundary>

export interface RuntimeBoundary {
  appBase: `/${string}`
  apiBase: `/${string}`
  websocketPath: `/${string}`
}

const browserStorageNamespacePattern = new RegExp(
  `^vmsh-179:v${BROWSER_STORAGE_NAMESPACE_VERSION}:(student|family|staff):` +
    String.raw`[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?$`,
)

export const browserStorageNamespaceSchema = z
  .string()
  .regex(browserStorageNamespacePattern)
  .brand<'BrowserStorageNamespace'>()
export type BrowserStorageNamespace = z.infer<typeof browserStorageNamespaceSchema>

export const runtimeConfigSchema = z
  .object({
    contractVersion: runtimeContractVersionSchema,
    audience: audienceSchema,
    appBase: z.string().startsWith('/'),
    apiBase: z.string().startsWith('/'),
    websocketPath: z.string().startsWith('/'),
    instance: runtimeInstanceSchema,
    serverTime: z.iso.datetime(),
    requestId: z.string().min(1),
    features: z
      .object({
        telegram: z.boolean(),
        google: z.boolean(),
        nats: z.boolean(),
        prototype: z.boolean(),
      })
      .strip(),
  })
  // Additive fields from a rolling backend deployment are ignored by an
  // older client. Required semantics change only behind contractVersion.
  .strip()
export type RuntimeConfig = z.infer<typeof runtimeConfigSchema>

/**
 * Turns the server-owned instance into the only browser-state namespace.
 * See `docs/runtime-isolation.md` and Phase 0's browser-storage isolation proof.
 */
export function createBrowserStorageNamespace(
  runtime: Pick<RuntimeConfig, 'audience' | 'instance'>,
): BrowserStorageNamespace {
  const audience = audienceSchema.parse(runtime.audience)
  const instance = runtimeInstanceSchema.parse(runtime.instance)
  return browserStorageNamespaceSchema.parse(
    `vmsh-179:v${BROWSER_STORAGE_NAMESPACE_VERSION}:${audience}:${instance}`,
  )
}

export function runtimeConfigSchemaForAudience(audience: Audience) {
  const expectedAudience = audienceSchema.parse(audience)
  const boundary = runtimeBoundaryByAudience[expectedAudience]
  return runtimeConfigSchema.extend({
    audience: z.literal(expectedAudience),
    appBase: z.literal(boundary.appBase),
    apiBase: z.literal(boundary.apiBase),
    websocketPath: z.literal(boundary.websocketPath),
  })
}

export function parseRuntimeConfigForAudience(audience: Audience, payload: unknown): RuntimeConfig {
  return runtimeConfigSchemaForAudience(audience).parse(payload)
}

export const apiErrorSchema = z
  .object({
    error: z
      .object({
        code: z.string().min(1),
        message: z.string().min(1),
        requestId: z.string().min(1),
        details: z.record(z.string(), z.unknown()).optional(),
      })
      .strip(),
  })
  .strip()
export type ApiError = z.infer<typeof apiErrorSchema>

export class ApiResponseError extends Error {
  readonly status: number
  readonly code: string
  readonly requestId: string
  readonly details?: Record<string, unknown>

  constructor(status: number, payload: ApiError) {
    super(payload.error.message)
    if (!Number.isInteger(status) || status < 400 || status > 599) {
      throw new RangeError('API error status must be an integer between 400 and 599')
    }
    this.name = 'ApiResponseError'
    this.status = status
    this.code = payload.error.code
    this.requestId = payload.error.requestId
    if (payload.error.details) this.details = payload.error.details
  }
}

const realtimeBaseSchema = z.object({
  cursor: z.number().int().nonnegative(),
  serverTime: z.iso.datetime(),
})

export const realtimeEventSchema = z.discriminatedUnion('type', [
  realtimeBaseSchema.extend({ type: z.literal('connected'), audience: audienceSchema }),
  realtimeBaseSchema.extend({ type: z.literal('pong') }),
  realtimeBaseSchema.extend({
    type: z.literal('error'),
    code: z.string().min(1),
    message: z.string().min(1),
    requestId: z.string().min(1),
  }),
  realtimeBaseSchema.extend({
    type: z.literal('invalidate'),
    audience: audienceSchema.optional(),
    resources: z.array(z.string().min(1)).min(1),
    reason: z.string().min(1),
  }),
  realtimeBaseSchema.extend({ type: z.literal('resync-required'), reason: z.string().min(1) }),
])
export type RealtimeEvent = z.infer<typeof realtimeEventSchema>

export const offlineMutationSchema = z.object({
  idempotencyKey: z.uuid(),
  payloadHash: z.string().min(16).max(256),
  createdAtClient: z.iso.datetime(),
  timezoneOffsetMinutes: z
    .number()
    .int()
    .min(-14 * 60)
    .max(14 * 60),
})
export type OfflineMutation = z.infer<typeof offlineMutationSchema>

export const submissionImagePolicy = {
  maximumCount: 10,
  maximumLongEdgePixels: 1920,
  storedMediaType: 'image/webp',
  originalStored: false,
} as const

export const lessonDeadlinePolicy = {
  authoringTimeZone: 'Europe/Moscow',
  boundary: 'solution-publication',
  statisticsGraceDays: 7,
  suspiciousClockSkewMinutes: null,
} as const

export const sessionPolicy = {
  expiryAuthority: 'server' as const,
  cookie: {
    httpOnly: true,
    secure: true,
    sameSite: 'lax' as const,
  },
  cookieNames: {
    student: { access: 'vmsh_student_access', refresh: 'vmsh_student_refresh' },
    family: { access: 'vmsh_family_access', refresh: 'vmsh_family_refresh' },
    staff: { access: 'vmsh_staff_access', refresh: 'vmsh_staff_refresh' },
  },
} as const

export const sessionMetadataSchema = z.object({
  expiresAt: z.iso.datetime(),
})
export type SessionMetadata = z.infer<typeof sessionMetadataSchema>

export const queryKeys = {
  runtime: (audience: Audience) => ['runtime', audience] as const,
  currentUser: (audience: Audience) => ['session', audience] as const,
  lesson: (lessonId: string) => ['lessons', lessonId] as const,
  task: (taskId: string) => ['tasks', taskId] as const,
  news: (postId?: string) => ['news', postId ?? 'list'] as const,
} as const

export interface FetchRuntimeOptions {
  fetchImplementation?: typeof globalThis.fetch
  signal?: AbortSignal
}

/**
 * Fetches only the compile-time audience endpoint and validates every boundary
 * before protected routes can mount. See `dev/development-plan/04-phase-0-baseline.md`.
 */
export async function fetchRuntime(
  audience: Audience,
  options: FetchRuntimeOptions = {},
): Promise<RuntimeConfig> {
  const expectedAudience = audienceSchema.parse(audience)
  const boundary = runtimeBoundaryByAudience[expectedAudience]
  const fetchImplementation = options.fetchImplementation ?? globalThis.fetch
  const response = await fetchImplementation(`${boundary.apiBase}/runtime`, {
    credentials: 'include',
    headers: { Accept: 'application/json' },
    ...(options.signal ? { signal: options.signal } : {}),
  })
  const payload: unknown = await response.json()
  if (!response.ok) throw new ApiResponseError(response.status, apiErrorSchema.parse(payload))
  return parseRuntimeConfigForAudience(expectedAudience, payload)
}

const runtimeContractFixtureBaseSchema = z
  .object({
    fixtureVersion: runtimeContractVersionSchema,
    request: z
      .object({
        method: z.literal('GET'),
        audience: audienceSchema,
        path: z.string().startsWith('/'),
      })
      .strict(),
    response: runtimeConfigSchema,
    browserStorageNamespace: browserStorageNamespaceSchema,
  })
  .strict()

export const runtimeContractFixtureSchema = runtimeContractFixtureBaseSchema.superRefine(
  (fixture, context) => {
    const expectedBoundary = runtimeBoundaryByAudience[fixture.request.audience]
    const expectedPath = `${expectedBoundary.apiBase}/runtime`
    if (fixture.request.path !== expectedPath) {
      context.addIssue({
        code: 'custom',
        message: `Runtime fixture path must be ${expectedPath}`,
        path: ['request', 'path'],
      })
    }

    const runtimeResult = runtimeConfigSchemaForAudience(fixture.request.audience).safeParse(
      fixture.response,
    )
    if (!runtimeResult.success) {
      for (const issue of runtimeResult.error.issues) {
        context.addIssue({
          ...issue,
          path: ['response', ...issue.path],
        })
      }
      return
    }

    const expectedNamespace = createBrowserStorageNamespace(runtimeResult.data)
    if (fixture.browserStorageNamespace !== expectedNamespace) {
      context.addIssue({
        code: 'custom',
        message: `Runtime fixture namespace must be ${expectedNamespace}`,
        path: ['browserStorageNamespace'],
      })
    }
  },
)
export type RuntimeContractFixture = z.infer<typeof runtimeContractFixtureSchema>

export const apiErrorContractFixtureSchema = z
  .object({
    fixtureVersion: runtimeContractVersionSchema,
    httpStatus: z.number().int().min(400).max(599),
    response: apiErrorSchema,
  })
  .strict()
export type ApiErrorContractFixture = z.infer<typeof apiErrorContractFixtureSchema>
