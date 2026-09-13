import { describe, expect, it, vi } from 'vitest'
import { ApiResponseError } from '@vmsh/contracts'
import { reportHandledError, setObservabilityUser, submissionFailureMessage } from './observability'
import * as Sentry from '@sentry/react'

vi.mock('@sentry/react', () => ({ captureException: vi.fn(), setUser: vi.fn() }))
const failure = (status: number) =>
  new ApiResponseError(status, {
    error: { code: 'service_unavailable', message: 'secret answer', requestId: 'req-42' },
  })

describe('submission error diagnostics', () => {
  it('distinguishes server failures, auth, rate limits and ambiguous transport failures', () => {
    expect(submissionFailureMessage(failure(503))).toContain('не проблема вашего интернета')
    expect(submissionFailureMessage(failure(503))).toContain('req-42')
    expect(submissionFailureMessage(failure(401))).toContain('Войдите снова')
    expect(submissionFailureMessage(failure(429))).toContain('Слишком много')
    expect(submissionFailureMessage(undefined, 'api:503:unavailable:request=req-42')).toContain(
      'Ошибка сервера',
    )
    expect(submissionFailureMessage(undefined, 'client:TestSubmissionNetworkError')).toContain(
      'недоступность сервера',
    )
    expect(submissionFailureMessage(undefined, 'client:TestSubmissionTimeoutError')).toContain(
      '30 секунд',
    )
    expect(submissionFailureMessage(undefined, 'client:stale-sending-lease')).toContain(
      'Ответ сохранён',
    )
    expect(submissionFailureMessage(undefined, 'client:TypeError')).toContain('Ошибка приложения')
    expect(submissionFailureMessage()).not.toContain('появится сеть')
  })
  it('reports identifiers but not error message/details, and deduplicates the same error', () => {
    const error = failure(503)
    reportHandledError(error, 'test.submit', {
      accountId: 'a-1',
      problemId: 'p-2',
      outboxId: 'queued-3',
      attempts: 2,
    })
    reportHandledError(error, 'query')
    expect(Sentry.captureException).toHaveBeenCalledTimes(1)
    const [safeError, context] = vi.mocked(Sentry.captureException).mock.calls[0]!
    expect(String(safeError)).not.toContain('secret')
    expect(context).toMatchObject({
      user: { id: 'a-1' },
      extra: { requestId: 'req-42', problemId: 'p-2', attempts: 2 },
    })
    expect(JSON.stringify(context)).not.toContain('secret')
    setObservabilityUser('a-1')
    setObservabilityUser(null)
    expect(Sentry.setUser).toHaveBeenLastCalledWith(null)
  })
})
