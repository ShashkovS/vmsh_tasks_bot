import { describe, expect, it, vi } from 'vitest'

import moderationFixture from '@vmsh/contracts/fixtures/news/moderation.v1.json'
import runtimeFixture from '@vmsh/contracts/fixtures/runtime/staff.v1.json'
import { runtimeConfigSchemaForAudience } from '@vmsh/contracts'

import { createNewsModerationClient } from './news-moderation-client'

const runtime = runtimeConfigSchemaForAudience('staff').parse(runtimeFixture.response)

describe('news moderation client', () => {
  it('lists and hides with the current visibility version', async () => {
    const hidden = { ...moderationFixture.items[0]!, visibility: 'manual_hidden', version: 2 }
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(Response.json(moderationFixture))
      .mockResolvedValueOnce(
        Response.json({ schemaVersion: 1, item: hidden, requestId: 'request-hide' }),
      )
    const client = createNewsModerationClient(runtime, { fetchImplementation })

    expect((await client.list('all')).items).toHaveLength(3)
    await client.changeVisibility('news.visible', 1, {
      schemaVersion: 1,
      state: 'manual_hidden',
      reason: null,
    })

    expect(fetchImplementation.mock.calls[0]?.[0]).toBe('/staff/api/v1/news?state=all&limit=100')
    expect(fetchImplementation.mock.calls[1]?.[1]).toEqual(
      expect.objectContaining({
        method: 'PATCH',
        headers: expect.objectContaining({ 'If-Match': '"news.visible:v1"' }),
      }),
    )
  })
})
