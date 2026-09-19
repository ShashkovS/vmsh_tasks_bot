import { describe, expect, it, vi } from 'vitest'

import feedFixture from '@vmsh/contracts/fixtures/news/feed.v1.json'
import runtimeFixture from '@vmsh/contracts/fixtures/runtime/student.v1.json'
import { runtimeConfigSchemaForAudience } from '@vmsh/contracts'

import { createNewsClient } from './news-client'

const runtime = runtimeConfigSchemaForAudience('student').parse(runtimeFixture.response)

describe('news client', () => {
  it('reads a cursor page and a single post from the Student boundary', async () => {
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(Response.json(feedFixture))
      .mockResolvedValueOnce(
        Response.json({
          schemaVersion: 1,
          item: feedFixture.items[0],
          requestId: 'request-news-post',
        }),
      )
    const client = createNewsClient(runtime, 'student', { fetchImplementation })

    expect((await client.list({ cursor: 'news.previous', limit: 10 })).items).toHaveLength(1)
    expect((await client.post('news.course-41')).item.postId).toBe('news.course-41')
    expect(fetchImplementation.mock.calls[0]?.[0]).toBe(
      '/student/api/v1/news?limit=10&contentVersion=2&cursor=news.previous',
    )
    expect(fetchImplementation.mock.calls[1]?.[0]).toBe(
      '/student/api/v1/news/news.course-41?contentVersion=2',
    )
  })

  it('refreshes once after an expired access cookie', async () => {
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(Response.json(feedFixture))
    const refreshSession = vi.fn(() => Promise.resolve())

    await createNewsClient(runtime, 'student', {
      fetchImplementation,
      refreshSession,
    }).list()

    expect(refreshSession).toHaveBeenCalledOnce()
    expect(fetchImplementation).toHaveBeenCalledTimes(2)
  })

  it('ignores additive response fields', async () => {
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(Response.json({ ...feedFixture, unexpected: true }))

    await expect(
      createNewsClient(runtime, 'student', { fetchImplementation }).list(),
    ).resolves.toEqual(feedFixture)
  })
})
