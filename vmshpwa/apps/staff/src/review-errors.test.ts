import { describe, expect, it } from 'vitest'

import { ApiResponseError } from '@vmsh/contracts'

import { describeReviewError } from './review-errors'

function apiError(code: string, message = 'Ошибка проверки') {
  return new ApiResponseError(409, {
    error: { code, message, requestId: 'request-test' },
  })
}

describe('describeReviewError', () => {
  it('distinguishes another teacher claim from an expired own lease', () => {
    expect(describeReviewError(apiError('review_already_claimed'))).toContain(
      'другой преподаватель',
    )
    expect(describeReviewError(apiError('review_lease_lost'))).toContain(
      'Срок блокировки работы истёк',
    )
  })

  it('explains changed submission evidence separately', () => {
    expect(describeReviewError(apiError('review_thread_changed'))).toContain(
      'школьник дополнил работу',
    )
  })

  it('keeps the server message for an unknown conflict', () => {
    expect(describeReviewError(apiError('review_unknown', 'Точная ошибка'))).toBe(
      'Точная ошибка Код обращения: request-test.',
    )
  })
})
