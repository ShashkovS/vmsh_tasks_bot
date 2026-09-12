import { describe, expect, it } from 'vitest'

import {
  sanitizeSentryBreadcrumb,
  sanitizeSentryEvent,
  submissionFailureMessage,
} from './observability'

it('explains persisted business limits without network advice or diagnostic identifiers', () => {
  for (const status of [429, 422]) {
    const hour = submissionFailureMessage(
      undefined,
      `api:${status}:test_attempt_hour_limit:request=secret-id`,
    )
    expect(hour).toContain('на текущий час')
    expect(hour).not.toMatch(/Код:|secret-id|запросов|интернет/)
    expect(submissionFailureMessage(undefined, `api:${status}:test_attempt_day_limit`)).toContain(
      'завтра',
    )
  }
})

describe('Sentry privacy boundary', () => {
  it('keeps only account ID and removes request contents while keeping the route', () => {
    const sanitized = sanitizeSentryEvent({
      user: { id: 'student-17', email: 'student@example.test' },
      request: {
        url: 'https://vmsh.example/student/tasks?student=17#answer',
        cookies: { vmsh_student_access: 'secret-cookie' },
        headers: { authorization: 'Bearer secret' },
        data: { answer: '179' },
        env: { REMOTE_ADDR: '192.0.2.1' },
      },
      extra: {
        requestId: 'request-17',
        telegramToken: 'secret-token',
        nested: { teacherComment: 'Точный текст комментария' },
      },
      contexts: {
        product: {
          courseId: 'math-57',
          photoUrl: 'https://media.example/sol_imgs/user_17/private.webp',
        },
      },
    })

    expect(sanitized.user).toEqual({ id: 'student-17' })
    expect(sanitized.request).toEqual({ url: 'https://vmsh.example/student/tasks' })
    expect(sanitized.extra).toEqual({
      requestId: 'request-17',
      telegramToken: '[redacted]',
      nested: { teacherComment: '[redacted]' },
    })
    expect(sanitized.contexts?.product).toEqual({
      courseId: 'math-57',
      photoUrl: '[redacted]',
    })
  })

  it('drops interaction text and secret breadcrumb data', () => {
    expect(
      sanitizeSentryBreadcrumb({
        category: 'ui.click',
        message: 'Ответ: 179',
        data: {
          target: 'button',
          submissionText: 'Моё решение',
          url: 'https://vmsh.example/student/tasks?search=Иванов',
        },
      }),
    ).toEqual({
      category: 'ui.click',
      message: '[redacted]',
      data: {
        target: 'button',
        submissionText: '[redacted]',
        url: 'https://vmsh.example/student/tasks',
      },
    })
  })
})
