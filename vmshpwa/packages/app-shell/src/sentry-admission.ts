import type { Event } from '@sentry/react'
import { sentryAdmissionRequestSchema, sentryAdmissionResponseSchema } from '@vmsh/contracts'
import { sentryEventSignature } from './sentry-noise'

/** Shared reservation, not a per-tab quota; docs/performance/2026-10-11-sentry-quota.md. */
export function createSentryAdmission(
  audience: 'student' | 'family' | 'staff',
  options: { fetch?: typeof globalThis.fetch } = {},
): (event: Event) => Promise<boolean> {
  const send = options.fetch ?? ((...args) => globalThis.fetch(...args))
  return async (event) => {
    const telemetry = event.extra?.telemetry
    const lane =
      telemetry !== null &&
      typeof telemetry === 'object' &&
      'lane' in telemetry &&
      telemetry.lane === 'query'
        ? 'query'
        : 'error'
    try {
      const response = await send(`/${audience}/api/v1/observability/sentry-admission`, {
        method: 'POST',
        credentials: 'omit',
        mode: 'same-origin',
        redirect: 'error',
        cache: 'no-store',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(
          sentryAdmissionRequestSchema.parse({ lane, signature: sentryEventSignature(event) }),
        ),
        signal: AbortSignal.timeout(2_000),
      })
      if (!response.ok) return false
      return sentryAdmissionResponseSchema.parse(await response.json()).allowed
    } catch {
      // No retry or capture here: backend unavailability must not burn Sentry quota.
      return false
    }
  }
}
