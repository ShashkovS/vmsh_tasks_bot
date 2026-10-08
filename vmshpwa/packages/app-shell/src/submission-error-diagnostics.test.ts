import { describe, expect, it, vi } from 'vitest'
import { ApiResponseError } from '@vmsh/contracts'
import {
  isSubmissionDeadlineFailure,
  reportHandledError,
  setObservabilityUser,
  submissionFailureMessage,
} from './observability'
import * as Sentry from '@sentry/react'

vi.mock('@sentry/react', () => ({ captureException: vi.fn(), setUser: vi.fn() }))
const failure = (status: number) =>
  new ApiResponseError(status, {
    error: { code: 'service_unavailable', message: 'secret answer', requestId: 'req-42' },
  })

describe('submission error diagnostics', () => {
  it('treats direct and persisted deadline failures as an expected closed window', () => {
    const direct = new ApiResponseError(409, {
      error: {
        code: 'submission_deadline_passed',
        message: 'internal deadline message',
        requestId: 'request-deadline',
      },
    })
    const persisted = 'api:409:submission_deadline_passed:request=request-deadline'

    expect(isSubmissionDeadlineFailure(direct)).toBe(true)
    expect(isSubmissionDeadlineFailure(undefined, persisted)).toBe(true)
    expect(isSubmissionDeadlineFailure(failure(409))).toBe(false)
    for (const message of [
      submissionFailureMessage(direct),
      submissionFailureMessage(undefined, persisted),
    ]) {
      expect(message).toBe(
        'Срок сдачи закончился, поэтому ответ не отправлен. Черновик сохранён на этом устройстве.',
      )
      expect(message).not.toMatch(/api:|409|request-deadline|internal deadline message/i)
    }
  })

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
