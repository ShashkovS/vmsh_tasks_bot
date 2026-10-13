import { describe, expect, it, vi } from 'vitest'

import {
  isAudienceRoute,
  openPushNotification,
  parseAudiencePushPayload,
} from './push-notification'

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

it('opens the absolute deep link immediately without querying or navigating old windows', async () => {
  const focus = vi.fn().mockResolvedValue(undefined)
  const openWindow = vi.fn().mockResolvedValue({ focus })
  const opening = openPushNotification({ openWindow }, 'https://school.test', 'student', {
    route: '/student/organizers/q-1',
  })
  expect(openWindow).toHaveBeenCalledWith('https://school.test/student/organizers/q-1')
  await opening
  expect(focus).toHaveBeenCalledOnce()
})
it.each([
  '/family/organizers/q-1',
  '/student/../staff/',
  'https://evil.test/student/',
  '/student/../../outside',
])('rejects escaped or foreign route %s', async (route) => {
  const openWindow = vi.fn()
  await openPushNotification({ openWindow }, 'https://school.test', 'student', { route })
  expect(openWindow).not.toHaveBeenCalled()
})
it('handles a null window and an unavailable focus after opening', async () => {
  await expect(
    openPushNotification(
      { openWindow: vi.fn().mockResolvedValue(null) },
      'https://school.test',
      'family',
      { route: '/family/organizers/q-1' },
    ),
  ).resolves.toBeUndefined()
  const focus = vi.fn().mockRejectedValue(new Error('Cannot focus'))
  await expect(
    openPushNotification(
      { openWindow: vi.fn().mockResolvedValue({ focus }) },
      'https://school.test',
      'family',
      { route: '/family/organizers/q-1' },
    ),
  ).resolves.toBeUndefined()
})
