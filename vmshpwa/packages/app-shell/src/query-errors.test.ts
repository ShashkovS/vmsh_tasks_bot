import { ApiResponseError, ServiceTransportError } from '@vmsh/contracts'
import { expect, it, vi } from 'vitest'
import * as Sentry from '@sentry/react'
import { reportHandledError } from './observability'
import { queryFamily, retryQuery } from './query-errors'

vi.mock('@sentry/react', () => ({ captureException: vi.fn() }))

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

it('omits controlled recovery but retains unexplained aborts, deadlines and submission failures', () => {
  vi.mocked(Sentry.captureException).mockClear()
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
  expect(Sentry.captureException).toHaveBeenCalledTimes(4)
  expect(vi.mocked(Sentry.captureException).mock.calls[0]?.[1]).toMatchObject({
    tags: { query_family: 'content', transport_kind: 'deadline' },
  })
  expect(vi.mocked(Sentry.captureException).mock.calls[3]?.[1]).toMatchObject({
    tags: { transport_kind: 'aborted' },
  })
  expect(JSON.stringify(vi.mocked(Sentry.captureException).mock.calls)).not.toContain('secret')
})
