import { describe, expect, it } from 'vitest'

import eventsFixture from '../fixtures/notifications/events.v1.json'
import preferencesFixture from '../fixtures/notifications/preferences.v1.json'
import {
  notificationEventListResponseSchema,
  notificationPreferenceListResponseSchema,
  notificationQueryKeys,
  updateNotificationPreferenceRequestSchema,
} from './notifications'

describe('notification contracts', () => {
  it('validates events and all category defaults', () => {
    const events = notificationEventListResponseSchema.parse(eventsFixture)
    const preferences = notificationPreferenceListResponseSchema.parse(preferencesFixture)

    expect(events.items[0]?.payload.classroomName).toBe('202')
    expect(preferences.items).toHaveLength(9)
    expect(preferences.items.find((item) => item.category === 'oral_window')?.pushEnabled).toBe(
      false,
    )
  })

  it('rejects malformed time and unknown fields', () => {
    expect(() =>
      updateNotificationPreferenceRequestSchema.parse({
        schemaVersion: 1,
        category: 'news',
        inAppEnabled: true,
        pushEnabled: true,
        soundEnabled: true,
        quietStartsLocal: '25:00',
        quietEndsLocal: '09:00',
        timezone: 'Europe/Moscow',
      }),
    ).toThrow()
  })

  it('isolates query keys by account and unread filter', () => {
    const first = { audience: 'student' as const, accountId: 'student.one' }
    const second = { audience: 'student' as const, accountId: 'student.two' }
    expect(notificationQueryKeys.events(first)).not.toEqual(notificationQueryKeys.events(second))
    expect(notificationQueryKeys.events(first)).not.toEqual(
      notificationQueryKeys.events(first, true),
    )
  })
})
