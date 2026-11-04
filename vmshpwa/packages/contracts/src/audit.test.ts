import { describe, expect, it } from 'vitest'

import { auditEventSchema } from './audit'

// Production event ae-220 was written by an ops script with an explicit UTC offset;
// one such row must not make the whole /staff/audit page unreadable
// (dev/ui-audit-20261104/BACKLOG.md, phase 1A item 2).
const event = {
  eventId: 'ae-220',
  audience: 'system',
  action: 'course.metadata_model.update',
  objectType: 'course',
  objectId: 'vmsh',
  requestId: 'ops-owner-metadata-model-1',
  actor: { userId: null, accountId: null, displayName: 'ops' },
  before: null,
  after: { model: 'v2' },
}

describe('auditEventSchema', () => {
  it.each([
    '2026-11-03T10:00:00Z',
    '2026-11-03T10:00:00+00:00',
    '2026-11-03T13:00:00.123456+03:00',
  ])('accepts occurredAt %s', (occurredAt) => {
    expect(auditEventSchema.safeParse({ ...event, occurredAt }).success).toBe(true)
  })

  it('rejects a timestamp without a zone', () => {
    expect(
      auditEventSchema.safeParse({ ...event, occurredAt: '2026-11-03T10:00:00' }).success,
    ).toBe(false)
  })
})
