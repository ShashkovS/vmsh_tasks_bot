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

  it('accepts object types the client does not label yet', () => {
    // Production had account_batch/student/group_lesson events the enum did not list.
    for (const objectType of ['account_batch', 'group_lesson', 'future_type']) {
      expect(
        auditEventSchema.safeParse({ ...event, objectType, occurredAt: '2026-11-04T08:44:54Z' })
          .success,
      ).toBe(true)
    }
  })

  it('rejects a timestamp without a zone', () => {
    expect(
      auditEventSchema.safeParse({ ...event, occurredAt: '2026-11-03T10:00:00' }).success,
    ).toBe(false)
  })
})
