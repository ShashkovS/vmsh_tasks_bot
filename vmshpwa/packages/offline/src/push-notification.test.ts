import { describe, expect, it } from 'vitest'

import { isAudienceRoute, parseAudiencePushPayload } from './push-notification'

const payload = {
  schemaVersion: 1,
  eventId: 'notification.review-one',
  category: 'review_completed',
  title: 'Проверка завершена',
  body: 'Проверены три задачи',
  route: '/student/tasks/problem-one',
  silent: false,
  occurredAt: '2026-10-05T12:00:00Z',
}

describe('audience push payload', () => {
  it('accepts only a valid payload inside the worker audience', () => {
    expect(parseAudiencePushPayload(JSON.stringify(payload), 'student')).toEqual(payload)
    expect(parseAudiencePushPayload(JSON.stringify(payload), 'family')).toBeNull()
    expect(parseAudiencePushPayload('{broken', 'student')).toBeNull()
  })

  it('keeps notification clicks inside the audience base', () => {
    expect(isAudienceRoute('/family/children/child-one', 'family')).toBe(true)
    expect(isAudienceRoute('/student/tasks/problem-one', 'family')).toBe(false)
    expect(isAudienceRoute('https://example.test/family/', 'family')).toBe(false)
  })
})
