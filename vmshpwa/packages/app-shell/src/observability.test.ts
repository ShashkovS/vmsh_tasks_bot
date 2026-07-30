import { describe, expect, it } from 'vitest'

import { sanitizeSentryBreadcrumb, sanitizeSentryEvent } from './observability'

describe('Sentry privacy boundary', () => {
  it('removes browser identity and request contents while keeping the route', () => {
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

    expect(sanitized.user).toBeUndefined()
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
