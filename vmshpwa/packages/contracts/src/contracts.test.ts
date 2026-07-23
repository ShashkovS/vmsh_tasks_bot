import { describe, expect, it } from 'vitest'

import {
  lessonDeadlinePolicy,
  offlineMutationSchema,
  queryKeys,
  realtimeEventSchema,
  runtimeConfigSchema,
  sessionPolicy,
  submissionImagePolicy,
} from './index'

describe('runtime contracts', () => {
  it('accepts an isolated student runtime', () => {
    expect(
      runtimeConfigSchema.parse({
        audience: 'student',
        appBase: '/student',
        apiBase: '/student/api/v1',
        websocketPath: '/student/ws',
        instance: 'agent',
        serverTime: '2026-07-22T12:00:00Z',
        requestId: 'req-1',
        features: { telegram: false, google: false, nats: false, prototype: true },
      }).instance,
    ).toBe('agent')
  })

  it('rejects realtime events without cursor', () => {
    expect(() =>
      realtimeEventSchema.parse({ type: 'pong', serverTime: '2026-07-22T12:00:00Z' }),
    ).toThrow()
  })

  it('keeps stable query keys and the academic-year session boundary', () => {
    expect(queryKeys.task('21n.6a')).toEqual(['tasks', '21n.6a'])
    expect(sessionPolicy.expiresMonth).toBe(8)
    expect(sessionPolicy.expiresDay).toBe(10)
    expect(sessionPolicy.cookieNames.student.access).not.toBe(
      sessionPolicy.cookieNames.family.access,
    )
  })

  it('validates offline timing and content identity independently', () => {
    expect(
      offlineMutationSchema.parse({
        idempotencyKey: '123e4567-e89b-42d3-a456-426614174000',
        payloadHash: 'sha256:0123456789abcdef',
        createdAtClient: '2026-07-26T09:59:00Z',
        timezoneOffsetMinutes: -180,
      }).payloadHash,
    ).toBe('sha256:0123456789abcdef')
    expect(lessonDeadlinePolicy.authoringTimeZone).toBe('Europe/Moscow')
    expect(lessonDeadlinePolicy.suspiciousClockSkewMinutes).toBeNull()
    expect(submissionImagePolicy.maximumLongEdgePixels).toBe(1920)
  })
})
