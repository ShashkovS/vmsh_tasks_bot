import { describe, expect, it, vi } from 'vitest'

import runtimeFixture from '@vmsh/contracts/fixtures/runtime/staff.v1.json'
import { auditListResponseSchema, runtimeConfigSchemaForAudience } from '@vmsh/contracts'

import { createAuditClient } from './audit-client'

const runtime = runtimeConfigSchemaForAudience('staff').parse(runtimeFixture.response)
const response = auditListResponseSchema.parse({
  schemaVersion: 1,
  items: [
    {
      eventId: 'audit.event-1',
      occurredAt: '2026-08-02T10:30:00Z',
      audience: 'staff',
      action: 'account.status_changed',
      objectType: 'account',
      objectId: 'account.student-1',
      requestId: 'request-1',
      actor: {
        userId: 'user.admin-1',
        accountId: 'account.admin-1',
        displayName: 'Петрова Анна',
      },
      before: { status: 'active' },
      after: { status: 'blocked', version: 2 },
    },
  ],
  nextCursor: null,
  requestId: 'request-list',
})

describe('audit client', () => {
  it('encodes validated filters and parses the strict response', async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(Response.json(response))
    const client = createAuditClient(runtime, { fetchImplementation })

    await expect(
      client.list({ objectType: 'account', query: ' request-1 ', cursor: 'audit.cursor-1' }),
    ).resolves.toEqual(response)
    expect(fetchImplementation.mock.calls[0]?.[0]).toBe(
      '/staff/api/v1/audit?objectType=account&q=request-1&limit=50&cursor=audit.cursor-1',
    )
    expect(fetchImplementation.mock.calls[0]?.[1]).toEqual(
      expect.objectContaining({ credentials: 'include', method: 'GET' }),
    )
  })

  it('rejects an unsafe response shape', async () => {
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValue(Response.json({ ...response, items: [{ password: 'secret' }] }))
    const client = createAuditClient(runtime, { fetchImplementation })

    await expect(client.list({ objectType: 'all', query: '', cursor: null })).rejects.toThrow()
  })

  it('accepts catalog and Telegram binding object filters', async () => {
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockImplementation(() => Promise.resolve(Response.json(response)))
    const client = createAuditClient(runtime, { fetchImplementation })

    await client.list({ objectType: 'course', query: '', cursor: null })
    await client.list({ objectType: 'group', query: '', cursor: null })
    await client.list({ objectType: 'telegram_binding', query: '', cursor: null })

    expect(fetchImplementation.mock.calls.map((call) => call[0])).toEqual([
      '/staff/api/v1/audit?objectType=course&q=&limit=50',
      '/staff/api/v1/audit?objectType=group&q=&limit=50',
      '/staff/api/v1/audit?objectType=telegram_binding&q=&limit=50',
    ])
  })
})
