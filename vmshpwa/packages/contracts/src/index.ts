import { z } from 'zod'

export const audienceSchema = z.enum(['student', 'family', 'staff'])
export type Audience = z.infer<typeof audienceSchema>

export const runtimeConfigSchema = z.object({
  audience: audienceSchema,
  appBase: z.string().startsWith('/'),
  apiBase: z.string().startsWith('/'),
  websocketPath: z.string().startsWith('/'),
  instance: z.string().min(1),
  serverTime: z.iso.datetime(),
  requestId: z.string().min(1),
  features: z.object({
    telegram: z.boolean(),
    google: z.boolean(),
    nats: z.boolean(),
    prototype: z.boolean(),
  }),
})
export type RuntimeConfig = z.infer<typeof runtimeConfigSchema>

export const apiErrorSchema = z.object({
  error: z.object({
    code: z.string().min(1),
    message: z.string().min(1),
    requestId: z.string().min(1),
    details: z.record(z.string(), z.unknown()).optional(),
  }),
})
export type ApiError = z.infer<typeof apiErrorSchema>

export class ApiResponseError extends Error {
  readonly code: string
  readonly requestId: string
  readonly details?: Record<string, unknown>

  constructor(payload: ApiError) {
    super(payload.error.message)
    this.name = 'ApiResponseError'
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
    type: z.literal('invalidate'),
    audience: audienceSchema.optional(),
    resources: z.array(z.string().min(1)).min(1),
    reason: z.string().min(1),
  }),
  realtimeBaseSchema.extend({ type: z.literal('resync-required'), reason: z.string().min(1) }),
])
export type RealtimeEvent = z.infer<typeof realtimeEventSchema>

export const loginContractSchema = z.object({
  login: z.string().trim().min(1).max(128),
  password: z.string().min(1).max(512),
  audience: audienceSchema,
})
export type LoginContract = z.infer<typeof loginContractSchema>

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

export async function fetchRuntime(apiBase: string, signal?: AbortSignal): Promise<RuntimeConfig> {
  const response = await fetch(`${apiBase}/runtime`, {
    credentials: 'include',
    ...(signal ? { signal } : {}),
  })
  const payload: unknown = await response.json()
  if (!response.ok) throw new ApiResponseError(apiErrorSchema.parse(payload))
  return runtimeConfigSchema.parse(payload)
}
