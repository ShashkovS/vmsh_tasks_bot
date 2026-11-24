import type { Event } from '@sentry/react'
import type { queryFailure } from './query-errors'

const MINUTE = 60_000
const WINDOW = 15 * MINUTE
const MAX_SIGNATURES = 128

/** docs/performance/2026-10-10-sentry-noise.md: confirmed refusals, not all 4xx. */
export function expectedHandledFailure(
  failure: ReturnType<typeof queryFailure>,
  operation: string,
  family: string,
): boolean {
  if (operation === 'query' && failure.expected) return true
  const api = failure.api
  if (!api) return false
  if (api.status === 503 && ['service_updating', 'request_not_confirmed'].includes(api.code))
    return true
  if (operation === 'query')
    return (
      (api.status === 401 && ['authentication_required', 'session_revoked'].includes(api.code)) ||
      (family === 'oral' && api.status === 404 && api.code === 'oral_window_not_found')
    )
  if (operation !== 'mutation' && operation !== 'test.submit' && operation !== 'written.submit')
    return false
  return (
    (api.status === 409 && api.code === 'submission_deadline_passed') ||
    ([422, 429].includes(api.status) &&
      ['test_attempt_hour_limit', 'test_attempt_day_limit'].includes(api.code))
  )
}

type Lane = 'query' | 'error'
type Budget = { since: number; sent: number; suppressed: number }
type Signature = { sentAt: number; suppressed: number }
const LIMITS: Record<Lane, { total: number; repeat: number }> = {
  query: { total: 6, repeat: WINDOW },
  error: { total: 20, repeat: MINUTE },
}

// Only bounded hashes go to our admission endpoint; Sentry never receives these keys.
export function sentryEventSignature(event: Event): string {
  const grouping = event.fingerprint ?? [
    event.message,
    ...(event.exception?.values ?? []).map((exception) => [
      exception.type,
      exception.value,
      exception.stacktrace?.frames
        ?.slice(-5)
        .map((frame) => [
          frame.filename?.split(/[?#]/, 1)[0],
          frame.function,
          frame.lineno,
          frame.colno,
        ]),
    ]),
  ]
  const value = JSON.stringify(grouping)
  let hash = 2166136261
  for (let index = 0; index < value.length; index++)
    hash = Math.imul(hash ^ value.charCodeAt(index), 16777619)
  return (hash >>> 0).toString(16).padStart(8, '0')
}

/** SDK flood boundary before shared admission; see the 2026-10-11 quota decision. */
export function createSentryEventFilter(
  options: { now?: () => number } = {},
): <T extends Event>(event: T) => T | null {
  const now = options.now ?? Date.now
  const signatures = new Map<string, Signature>()
  const budgets: Record<Lane, Budget> = {
    query: { since: now(), sent: 0, suppressed: 0 },
    error: { since: now(), sent: 0, suppressed: 0 },
  }

  return (event) => {
    const unhandled = event.exception?.values?.some((value) => value.mechanism?.handled === false)
    if (!unhandled && event.tags?.operation === 'service.recovery') return null
    const lane: Lane = unhandled ? 'error' : event.tags?.operation === 'query' ? 'query' : 'error'
    const time = now()
    const budget = budgets[lane]
    if (time - budget.since >= WINDOW || time < budget.since) {
      budget.since = time
      budget.sent = 0
    }

    // Read transport and source-less synthetic TypeError are breadcrumbs only.
    if (
      lane === 'query' &&
      (['network', 'deadline'].includes(String(event.tags?.transport_kind)) ||
        (event.tags?.diagnostic_source !== 'original' &&
          event.exception?.values?.some((value) => value.value === 'PWA query: TypeError')))
    ) {
      budget.suppressed++
      return null
    }

    const key = `${lane}:${sentryEventSignature(event)}`
    const signature = signatures.get(key)
    if (signature && time >= signature.sentAt && time - signature.sentAt < LIMITS[lane].repeat) {
      signature.suppressed++
      budget.suppressed++
      return null
    }
    if (budget.sent >= LIMITS[lane].total) {
      budget.suppressed++
      return null
    }
    // Bounded memory even when browser extensions or a broken loop create unique errors.
    if (!signature && signatures.size >= MAX_SIGNATURES) {
      const oldest = signatures.keys().next().value
      if (oldest !== undefined) signatures.delete(oldest)
    }
    signatures.delete(key)
    signatures.set(key, { sentAt: time, suppressed: 0 })
    budget.sent++
    const suppressed = budget.suppressed
    budget.suppressed = 0
    return {
      ...event,
      tags: { ...event.tags, telemetry_policy: 'frontend-v2' },
      extra: {
        ...event.extra,
        telemetry: {
          lane,
          sampleRate: 1,
          windowSeconds: WINDOW / 1_000,
          repeatSeconds: LIMITS[lane].repeat / 1_000,
          suppressedSinceLastEvent: suppressed,
          sameSignatureSuppressed: signature?.suppressed ?? 0,
        },
      },
    }
  }
}
