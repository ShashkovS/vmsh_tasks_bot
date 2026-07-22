import { describe, expect, it, vi } from 'vitest'

import { createOutboxItem } from './index'

describe('offline outbox', () => {
  it('keeps the client creation time and an idempotency id', () => {
    vi.stubGlobal('crypto', { randomUUID: () => 'fixed-id' })
    const item = createOutboxItem(
      { ownerId: 'student-1', kind: 'written-answer', payload: { text: 'Доказательство' } },
      new Date('2026-07-26T09:59:00Z'),
    )
    expect(item.id).toBe('fixed-id')
    expect(item.createdAtClient).toBe('2026-07-26T09:59:00.000Z')
    expect(item.status).toBe('queued')
  })
})
