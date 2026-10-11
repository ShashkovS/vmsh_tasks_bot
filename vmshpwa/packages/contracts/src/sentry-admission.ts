import { z } from 'zod'

/** Public telemetry, no event content; docs/performance/2026-10-11-sentry-quota.md. */
export const sentryAdmissionRequestSchema = z
  .object({ lane: z.enum(['query', 'error']), signature: z.string().regex(/^[0-9a-f]{8}$/) })
  .strict()

export const sentryAdmissionResponseSchema = z.object({ allowed: z.boolean() }).strict()
