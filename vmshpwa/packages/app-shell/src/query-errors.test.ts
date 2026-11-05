import {
  ApiResponseError,
  ServiceTransportError,
  courseQueryKeys,
  oralWindowQueryKeys,
} from '@vmsh/contracts'
import { expect, it, vi } from 'vitest'
import * as Sentry from '@sentry/react'
import { reportHandledError } from './observability'
import { queryFamily, retryQuery } from './query-errors'

vi.mock('@sentry/react', () => ({ captureException: vi.fn(), addBreadcrumb: vi.fn() }))

it('does not retry expected offline/recovery/cancelled reads or HTTP client rejections', () => {
  for (const error of [
    new ServiceTransportError('offline'),
    new Error('wrapper', { cause: new ServiceTransportError('recovering') }),
    new DOMException('cancelled', 'AbortError'),
    new ApiResponseError(401, { error: { code: 'expired', message: 'expired', requestId: 'req' } }),
  ])
    expect(retryQuery(0, error)).toBe(false)
  for (const error of [
    new TypeError('bug'),
    new ServiceTransportError('deadline'),
    new ServiceTransportError('network'),
  ]) {
    expect(retryQuery(0, error)).toBe(true)
    expect(retryQuery(1, error)).toBe(false)
  }
})

it('keeps query families bounded without principal identifiers or arbitrary keys', () => {
  expect(queryFamily(['principal', 'student', 'secret-account', 'courses', 'p-1'])).toBe('courses')
  expect(queryFamily(['secret answer'])).toBe('other')
})

it('classifies actual contracts keys so oral refusals and offline diagnostics do not become other', () => {
  const principal = { audience: 'student' as const, accountId: 'a-secret' }
  expect(queryFamily(courseQueryKeys.home(principal))).toBe('courses')
  expect(queryFamily(courseQueryKeys.offlineLessons(principal))).toBe('offline')
  const oral = queryFamily(oralWindowQueryKeys.student(principal, 'c-secret', 'gl-secret'))
  expect(oral).toBe('oral')
  vi.mocked(Sentry.captureException).mockClear()
  reportHandledError(
    new ApiResponseError(404, {
      error: { code: 'oral_window_not_found', message: 'secret', requestId: 'req' },
    }),
    'query',
    { queryFamily: oral },
  )
  expect(Sentry.captureException).not.toHaveBeenCalled()
})

it('retains original public application locations without secret messages, functions or URLs', () => {
  vi.mocked(Sentry.captureException).mockClear()
  const cause = new TypeError('secret answer')
  cause.stack = [
    'TypeError: secret answer',
    `    at privateSolution (${location.origin}/student/assets/app-123.js?token=secret:88:217741)`,
    '    at https://untrusted.example/student/assets/secret.js:1:2',
    `    at ${location.origin}/student/api/v1/private-secret:3:4`,
  ].join('\n')
  reportHandledError(new Error('secret wrapper', { cause }), 'query', { queryFamily: 'offline' })
  expect(vi.mocked(Sentry.captureException).mock.calls[0]?.[0]).toMatchObject({
    message: 'PWA query: Error',
    stack: `Error: PWA query: Error\n    at ${location.origin}/student/assets/app-123.js:88:217741`,
  })
  expect(JSON.stringify(vi.mocked(Sentry.captureException).mock.calls)).not.toContain('secret')
})

it('keeps unknown bugs at different original locations in separate diagnostic groups', () => {
  vi.mocked(Sentry.captureException).mockClear()
  for (const line of [10, 20]) {
    const error = new TypeError('secret answer')
    error.stack = `TypeError: secret answer\n    at ${location.origin}/student/assets/app-123.js:${line}:1`
    reportHandledError(error, 'query', { queryFamily: 'offline' })
  }
  for (const [index, line] of [10, 20].entries())
    expect(vi.mocked(Sentry.captureException).mock.calls[index]?.[1]).toMatchObject({
      fingerprint: [
        'pwa-handled-v1',
        'query',
        'offline',
        'unknown',
        'TypeError',
        `/student/assets/app-123.js:${line}:1`,
      ],
    })
})

it('retains the first original location in Firefox and Safari stacks without an error header', () => {
  vi.mocked(Sentry.captureException).mockClear()
  const error = new TypeError('secret answer')
  error.stack = `privateSolution@${location.origin}/student/assets/app-123.js:10:1\n@${location.origin}/student/assets/app-123.js:20:2`
  reportHandledError(error, 'query', { queryFamily: 'offline' })
  expect(vi.mocked(Sentry.captureException).mock.calls[0]?.[0]).toMatchObject({
    stack: `Error: PWA query: TypeError\n    at ${location.origin}/student/assets/app-123.js:10:1\n    at ${location.origin}/student/assets/app-123.js:20:2`,
  })
  expect(vi.mocked(Sentry.captureException).mock.calls[0]?.[1]).toMatchObject({
    fingerprint: [
      'pwa-handled-v1',
      'query',
      'offline',
      'unknown',
      'TypeError',
      '/student/assets/app-123.js:10:1',
    ],
  })
})

it('groups by safe operation/family/kind instead of user, request or capture stack', () => {
  vi.mocked(Sentry.captureException).mockClear()
  for (const accountId of ['a-1', 'a-2'])
    reportHandledError(
      new ApiResponseError(503, {
        error: { code: 'unavailable', message: 'secret answer', requestId: `req-${accountId}` },
      }),
      'query',
      { accountId, queryFamily: 'content' },
    )
  reportHandledError(new TypeError('secret'), 'query', { queryFamily: 'courses' })
  const calls = vi.mocked(Sentry.captureException).mock.calls
  for (const index of [0, 1])
    expect(calls[index]?.[1]).toMatchObject({
      fingerprint: [
        'pwa-handled-v1',
        'query',
        'content',
        'api',
        'API failure',
        '503',
        'unavailable',
      ],
    })
  expect(calls).toHaveLength(2)
  expect(JSON.stringify(calls)).not.toContain('secret')
})

it('does not capture confirmed expected refusals but keeps HTTP bugs and submission auth failures', () => {
  vi.mocked(Sentry.captureException).mockClear()
  const api = (status: number, code: string) =>
    new ApiResponseError(status, { error: { code, message: 'secret', requestId: 'req' } })
  reportHandledError(api(401, 'authentication_required'), 'query')
  reportHandledError(api(404, 'oral_window_not_found'), 'query', { queryFamily: 'oral' })
  reportHandledError(api(422, 'test_attempt_hour_limit'), 'test.submit')
  reportHandledError(api(409, 'submission_deadline_passed'), 'written.submit')
  expect(Sentry.captureException).not.toHaveBeenCalled()
  reportHandledError(api(500, 'authentication_required'), 'query')
  reportHandledError(api(401, 'authentication_required'), 'test.submit')
  reportHandledError(api(429, 'too_many_requests'), 'test.submit')
  expect(Sentry.captureException).toHaveBeenCalledTimes(3)
})

it('keeps read deadlines and source-less TypeErrors as breadcrumbs, preserving aborts and writes', () => {
  vi.mocked(Sentry.captureException).mockClear()
  vi.mocked(Sentry.addBreadcrumb).mockClear()
  reportHandledError(
    new Error('secret wrapper', { cause: new ServiceTransportError('recovering') }),
    'query',
  )
  expect(Sentry.captureException).not.toHaveBeenCalled()
  reportHandledError(
    new Error('secret wrapper', {
      cause: new ServiceTransportError('deadline', new Error('secret answer URL')),
    }),
    'query',
    { queryFamily: 'content' },
  )
  reportHandledError(new TypeError('secret programming error'), 'query')
  reportHandledError(new ServiceTransportError('offline'), 'test.submit')
  reportHandledError(new DOMException('secret storage abort', 'AbortError'), 'query')
  expect(Sentry.captureException).toHaveBeenCalledTimes(2)
  expect(Sentry.addBreadcrumb).toHaveBeenCalledTimes(2)
  expect(vi.mocked(Sentry.captureException).mock.calls[1]?.[1]).toMatchObject({
    tags: { transport_kind: 'aborted' },
  })
  expect(JSON.stringify(vi.mocked(Sentry.captureException).mock.calls)).not.toContain('secret')
  expect(JSON.stringify(vi.mocked(Sentry.addBreadcrumb).mock.calls)).not.toContain('secret')
})

it('does not let a breadcrumb-only read consume a later submission diagnostic for the same error', () => {
  vi.mocked(Sentry.captureException).mockClear()
  vi.mocked(Sentry.addBreadcrumb).mockClear()
  const error = new TypeError('secret answer')
  reportHandledError(error, 'query')
  reportHandledError(error, 'query')
  expect(Sentry.addBreadcrumb).toHaveBeenCalledTimes(1)
  expect(Sentry.captureException).not.toHaveBeenCalled()
  reportHandledError(error, 'written.submit')
  expect(Sentry.captureException).toHaveBeenCalledTimes(1)
  expect(vi.mocked(Sentry.captureException).mock.calls[0]?.[1]).toMatchObject({
    tags: { operation: 'written.submit' },
  })
})
