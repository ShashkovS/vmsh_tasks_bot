import { describe, expect, it, vi } from 'vitest'

import moderationFixture from '@vmsh/contracts/fixtures/news/moderation.v1.json'
import runtimeFixture from '@vmsh/contracts/fixtures/runtime/staff.v1.json'
import { runtimeConfigSchemaForAudience } from '@vmsh/contracts'

import { createNewsModerationClient } from './news-moderation-client'

const runtime = runtimeConfigSchemaForAudience('staff').parse(runtimeFixture.response)

describe('news moderation client', () => {
  it('lists, hides and reconciles source state with the current version', async () => {
    const hidden = { ...moderationFixture.items[0]!, visibility: 'manual_hidden', version: 2 }
    const deleted = {
      ...moderationFixture.items[0]!,
      visibility: 'source_deleted',
      version: 3,
    }
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(Response.json(moderationFixture))
      .mockResolvedValueOnce(
        Response.json({ schemaVersion: 1, item: hidden, requestId: 'request-hide' }),
      )
      .mockResolvedValueOnce(
        Response.json({ schemaVersion: 1, item: deleted, requestId: 'request-source' }),
      )
      .mockResolvedValueOnce(
        Response.json({ schemaVersion: 1, item: hidden, requestId: 'request-local' }),
      )
      .mockResolvedValueOnce(
        Response.json({ schemaVersion: 1, item: hidden, requestId: 'request-edit-local' }),
      )
    const client = createNewsModerationClient(runtime, { fetchImplementation })

    expect((await client.list('all')).items).toHaveLength(3)
    await client.changeVisibility('news.visible', 1, {
      schemaVersion: 1,
      state: 'manual_hidden',
      reason: null,
    })
    await client.reconcileSource('news.visible', 2, {
      schemaVersion: 1,
      sourceState: 'deleted',
      reason: 'Проверено в Telegram',
    })
    await client.createLocal({
      schemaVersion: 1,
      ownerType: 'course',
      ownerId: 'course.math',
      text: 'Новая публикация',
      publishedAt: '2026-08-04T13:00:00Z',
    })
    await client.updateLocal('news.visible', 2, {
      schemaVersion: 1,
      text: 'Исправленная публикация',
      publishedAt: '2026-08-05T13:00:00Z',
    })

    expect(fetchImplementation.mock.calls[0]?.[0]).toBe('/staff/api/v1/news?state=all&limit=100')
    expect(fetchImplementation.mock.calls[1]?.[1]).toEqual(
      expect.objectContaining({
        method: 'PATCH',
        headers: expect.objectContaining({ 'If-Match': '"news.visible:v1"' }),
      }),
    )
    expect(fetchImplementation.mock.calls[2]?.[0]).toBe(
      '/staff/api/v1/news/news.visible/source-state',
    )
    expect(fetchImplementation.mock.calls[2]?.[1]).toEqual(
      expect.objectContaining({
        method: 'PATCH',
        headers: expect.objectContaining({ 'If-Match': '"news.visible:v2"' }),
      }),
    )
    expect(fetchImplementation.mock.calls[3]?.[0]).toBe('/staff/api/v1/news/local')
    expect(fetchImplementation.mock.calls[3]?.[1]).toEqual(
      expect.objectContaining({ method: 'POST' }),
    )
    expect(fetchImplementation.mock.calls[4]?.[0]).toBe('/staff/api/v1/news/news.visible/local')
    expect(fetchImplementation.mock.calls[4]?.[1]).toEqual(
      expect.objectContaining({
        method: 'PATCH',
        headers: expect.objectContaining({ 'If-Match': '"news.visible:v2"' }),
      }),
    )
  })
})
