import { describe, expect, it } from 'vitest'

import eventsFixture from '../fixtures/notifications/events.v1.json'
import preferencesFixture from '../fixtures/notifications/preferences.v1.json'
import {
  courseNotificationPreferenceListResponseSchema,
  deletePushSubscriptionRequestSchema,
  nativePushPayloadSchema,
  notificationEventListResponseSchema,
  notificationPreferenceListResponseSchema,
  notificationQueryKeys,
  pushSubscriptionConfigResponseSchema,
  savePushSubscriptionRequestSchema,
  updateNotificationPreferenceRequestSchema,
  updateCourseNotificationPreferenceRequestSchema,
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

  it('validates inherited and explicit course push preferences', () => {
    const items = preferencesFixture.items.map((item) => ({
      category: item.category,
      pushEnabled: item.pushEnabled,
      inherited: true,
      updatedAt: null,
    }))
    expect(
      courseNotificationPreferenceListResponseSchema.parse({
        schemaVersion: 1,
        courseId: 'course.math',
        items,
        requestId: 'request-course-preferences',
      }).items,
    ).toHaveLength(9)
    expect(
      updateCourseNotificationPreferenceRequestSchema.parse({
        schemaVersion: 1,
        category: 'news',
        pushEnabled: null,
      }).pushEnabled,
    ).toBeNull()
  })

  it('isolates query keys by account and unread filter', () => {
    const first = { audience: 'student' as const, accountId: 'student.one' }
    const second = { audience: 'student' as const, accountId: 'student.two' }
    expect(notificationQueryKeys.events(first)).not.toEqual(notificationQueryKeys.events(second))
    expect(notificationQueryKeys.events(first)).not.toEqual(
      notificationQueryKeys.events(first, true),
    )
  })

  it('validates browser subscription and native payload boundaries', () => {
    const p256dh = `B${'a'.repeat(86)}`
    const auth = 'b'.repeat(22)
    expect(
      savePushSubscriptionRequestSchema.parse({
        schemaVersion: 1,
        endpoint: 'https://push.example.test/device',
        expirationTime: null,
        keys: { p256dh, auth },
      }).endpoint,
    ).toBe('https://push.example.test/device')
    expect(() =>
      deletePushSubscriptionRequestSchema.parse({
        schemaVersion: 1,
        endpoint: 'http://push.example.test/device',
      }),
    ).toThrow()
    expect(() =>
      pushSubscriptionConfigResponseSchema.parse({
        schemaVersion: 1,
        enabled: true,
        applicationServerKey: null,
        requestId: 'request.push',
      }),
    ).toThrow()
    expect(
      nativePushPayloadSchema.parse({
        schemaVersion: 1,
        eventId: 'notification.review-one',
        category: 'review_completed',
        title: 'Проверка завершена',
        body: 'Проверены три задачи',
        route: '/student/tasks/problem-one',
        silent: true,
        occurredAt: '2026-10-05T12:00:00Z',
      }).silent,
    ).toBe(true)
  })
})
