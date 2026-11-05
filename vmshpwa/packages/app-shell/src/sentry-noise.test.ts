import type { Event } from '@sentry/react'
import { ApiResponseError, ServiceTransportError } from '@vmsh/contracts'
import { describe, expect, it } from 'vitest'
import { queryFailure } from './query-errors'
import { createSentryEventFilter, expectedHandledFailure } from './sentry-noise'

function api(status: number, code: string) {
  return queryFailure(
    new ApiResponseError(status, { error: { code, message: 'secret answer', requestId: 'req' } }),
  )
}

function event(signature = 'content', operation = 'query', kind = 'unknown'): Event {
  return {
    fingerprint: ['test', signature],
    tags: { operation, transport_kind: kind },
    exception: { values: [{ type: 'Error', value: 'safe diagnostic' }] },
  }
}

describe('confirmed expected refusals', () => {
  it('filters only known status/code/operation combinations', () => {
    for (const [status, code, operation, family] of [
      [401, 'authentication_required', 'query', 'courses'],
      [401, 'session_revoked', 'query', 'auth'],
      [404, 'oral_window_not_found', 'query', 'oral'],
      [409, 'submission_deadline_passed', 'test.submit', 'other'],
      [422, 'test_attempt_hour_limit', 'test.submit', 'other'],
      [429, 'test_attempt_day_limit', 'mutation', 'other'],
      [503, 'service_updating', 'query', 'runtime'],
      [503, 'request_not_confirmed', 'written.submit', 'other'],
    ] as const)
      expect(expectedHandledFailure(api(status, code), operation, family)).toBe(true)
    for (const [status, code, operation, family] of [
      [500, 'authentication_required', 'query', 'auth'],
      [401, 'authentication_required', 'test.submit', 'other'],
      [401, 'unexpected_auth_bug', 'query', 'auth'],
      [404, 'oral_window_not_found', 'query', 'courses'],
      [404, 'unexpected_missing_resource', 'query', 'oral'],
      [429, 'too_many_requests', 'test.submit', 'other'],
      [500, 'test_attempt_hour_limit', 'test.submit', 'other'],
      [422, 'test_attempt_hour_limit', 'test.storage', 'other'],
      [409, 'submission_deadline_passed', 'query', 'content'],
      [500, 'service_updating', 'query', 'runtime'],
    ] as const)
      expect(expectedHandledFailure(api(status, code), operation, family)).toBe(false)
    expect(
      expectedHandledFailure(queryFailure(new ServiceTransportError('offline')), 'query', 'other'),
    ).toBe(true)
    expect(
      expectedHandledFailure(
        queryFailure(new ServiceTransportError('offline')),
        'test.submit',
        'other',
      ),
    ).toBe(false)
  })
})

describe('SDK flood boundary', () => {
  it('coalesces 10,000 new objects and reports suppressed repeats at the next window', () => {
    let time = 0
    const filter = createSentryEventFilter({ now: () => time })
    expect(filter(event())).not.toBeNull()
    for (let repeat = 0; repeat < 10_000; repeat++) expect(filter(event())).toBeNull()
    time = 15 * 60_000
    const next = filter(event())
    expect(next?.extra?.telemetry).toMatchObject({
      suppressedSinceLastEvent: 10_000,
      sameSignatureSuppressed: 10_000,
    })
    expect(next?.tags?.telemetry_policy).toBe('frontend-v2')
  })

  it('does not let read/recovery floods consume submission, storage or crash budgets', () => {
    const filter = createSentryEventFilter({ now: () => 0 })
    for (let signature = 0; signature < 6; signature++)
      expect(filter(event(`query-${signature}`))).not.toBeNull()
    expect(filter(event('query-overflow'))).toBeNull()
    expect(filter(event('recovery', 'service.recovery'))).toBeNull()
    expect(filter(event('different-recovery', 'service.recovery'))).toBeNull()
    expect(filter(event('submission', 'test.submit'))).not.toBeNull()
    expect(filter(event('storage', 'written.storage'))).not.toBeNull()
    expect(
      filter({
        ...event('crash'),
        exception: {
          values: [{ type: 'TypeError', mechanism: { type: 'onerror', handled: false } }],
        },
      }),
    ).not.toBeNull()
  })

  it('bounds unique automatic errors, resets the budget and distinguishes error locations', () => {
    let time = 0
    const filter = createSentryEventFilter({ now: () => time })
    const crash = (line: number): Event => ({
      exception: {
        values: [
          {
            type: 'TypeError',
            value: 'unexpected programming error',
            stacktrace: { frames: [{ filename: '/app.js', lineno: line }] },
          },
        ],
      },
    })
    for (let line = 0; line < 20; line++) expect(filter(crash(line))).not.toBeNull()
    for (let line = 20; line < 1_000; line++) expect(filter(crash(line))).toBeNull()
    time = 15 * 60_000
    expect(filter(crash(1_000))?.extra?.telemetry).toMatchObject({
      lane: 'error',
      suppressedSinceLastEvent: 980,
    })
  })

  it('drops read transport events while preserving unexpected aborts, useful errors and writes', () => {
    const filter = createSentryEventFilter()
    expect(filter(event('network', 'query', 'network'))).toBeNull()
    expect(filter(event('deadline', 'query', 'deadline'))).toBeNull()
    expect(filter(event('type-error'))).not.toBeNull()
    expect(filter(event('abort', 'query', 'aborted'))).not.toBeNull()
    expect(filter(event('api', 'query', 'api'))).not.toBeNull()
    expect(filter(event('write-network', 'written.submit', 'network'))).not.toBeNull()
  })

  it('drops 10,000 source-less query TypeErrors but keeps original bugs and unhandled TypeErrors', () => {
    const filter = createSentryEventFilter()
    const synthetic = {
      ...event('type-error'),
      exception: { values: [{ type: 'Error', value: 'PWA query: TypeError' }] },
    }
    for (let index = 0; index < 10_000; index++) expect(filter(synthetic)).toBeNull()
    expect(
      filter({ ...synthetic, tags: { ...synthetic.tags, diagnostic_source: 'original' } }),
    ).not.toBeNull()
    expect(
      filter({
        ...synthetic,
        exception: {
          values: [{ type: 'TypeError', mechanism: { type: 'onerror', handled: false } }],
        },
      }),
    ).not.toBeNull()
  })

  it('retains distinct automatic errors after their repeat interval without changing SDK grouping', () => {
    let time = 0
    const filter = createSentryEventFilter({ now: () => time })
    const automatic: Event = { message: 'unexpected error', tags: { audience: 'student' } }
    expect(filter(automatic)?.fingerprint).toBeUndefined()
    expect(filter({ ...automatic })).toBeNull()
    time = 60_000
    expect(filter(automatic)?.extra?.telemetry).toMatchObject({ sameSignatureSuppressed: 1 })
    expect(automatic).toEqual({ message: 'unexpected error', tags: { audience: 'student' } })
  })
})
