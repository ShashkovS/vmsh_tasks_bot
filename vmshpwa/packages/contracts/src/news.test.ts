import { describe, expect, it } from 'vitest'

import feedFixture from '../fixtures/news/feed.v1.json'
import { newsFeedResponseSchema, newsQueryKeys } from './news'

describe('news contracts', () => {
  it('validates a paginated rich-text feed', () => {
    const feed = newsFeedResponseSchema.parse(feedFixture)

    expect(feed.items[0]?.blocks[0]?.entities?.[0]).toEqual({
      type: 'bold',
      offset: 3,
      length: 1,
    })
    expect(feed.nextCursor).toBe('news.course-41')
  })

  it('rejects unchecked media URLs and isolates account query keys', () => {
    expect(() =>
      newsFeedResponseSchema.parse({
        ...feedFixture,
        items: [
          {
            ...feedFixture.items[0],
            media: [{ ...feedFixture.items[0]!.media[0], previewUrl: 'javascript:alert(1)' }],
          },
        ],
      }),
    ).toThrow()

    expect(newsQueryKeys.feed({ audience: 'student', accountId: 'student.one' })).not.toEqual(
      newsQueryKeys.feed({ audience: 'student', accountId: 'student.two' }),
    )
  })
})
