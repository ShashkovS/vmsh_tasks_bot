import { describe, expect, it, vi } from 'vitest'

import { classifyIdempotencyReplay, createOutboxItem } from './index'

describe('offline outbox', () => {
  it('keeps the client creation time and an idempotency id', () => {
    vi.stubGlobal('crypto', { randomUUID: () => 'fixed-id' })
    const item = createOutboxItem(
      {
        ownerId: 'student-1',
        kind: 'written-answer',
        payload: { text: 'Доказательство' },
        payloadHash: 'sha256:answer-1',
        timezoneOffsetMinutes: -180,
      },
      new Date('2026-07-26T09:59:00Z'),
    )
    expect(item.id).toBe('fixed-id')
    expect(item.idempotencyKey).toBe('fixed-id')
    expect(item.payloadHash).toBe('sha256:answer-1')
    expect(item.timezoneOffsetMinutes).toBe(-180)
    expect(item.createdAtClient).toBe('2026-07-26T09:59:00.000Z')
    expect(item.status).toBe('queued')
  })

  it('replays only the same payload for an existing idempotency key', () => {
    expect(classifyIdempotencyReplay('sha256:a', 'sha256:a')).toBe('replay')
    expect(classifyIdempotencyReplay('sha256:a', 'sha256:b')).toBe('conflict')
  })
})
