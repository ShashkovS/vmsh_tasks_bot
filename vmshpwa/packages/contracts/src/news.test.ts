import { describe, expect, it } from 'vitest'

import feedFixture from '../fixtures/news/feed.v1.json'
import moderationFixture from '../fixtures/news/moderation.v1.json'
import {
  changeNewsVisibilityRequestSchema,
  createLocalNewsRequestSchema,
  newsFeedResponseSchema,
  newsQueryKeys,
  reconcileNewsSourceRequestSchema,
  staffNewsListResponseSchema,
} from './news'

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

  it('validates Staff moderation rows and visibility commands', () => {
    const list = staffNewsListResponseSchema.parse(moderationFixture)
    expect(list.items.map((item) => item.visibility)).toEqual([
      'visible',
      'manual_hidden',
      'source_deleted',
    ])
    expect(() =>
      changeNewsVisibilityRequestSchema.parse({
        schemaVersion: 1,
        state: 'visible',
        reason: 'old reason',
      }),
    ).toThrow()
    expect(
      reconcileNewsSourceRequestSchema.parse({
        schemaVersion: 1,
        sourceState: 'deleted',
        reason: 'Пост отсутствует в канале',
      }).sourceState,
    ).toBe('deleted')
    expect(() =>
      reconcileNewsSourceRequestSchema.parse({
        schemaVersion: 1,
        sourceState: 'present',
        reason: '   ',
      }),
    ).toThrow()
    expect(
      createLocalNewsRequestSchema.parse({
        schemaVersion: 1,
        ownerType: 'group',
        ownerId: 'group.beginners',
        text: 'Разбор сегодня в 17:00',
        publishedAt: '2026-08-04T13:00:00Z',
      }).text,
    ).toBe('Разбор сегодня в 17:00')
    expect(() =>
      createLocalNewsRequestSchema.parse({
        schemaVersion: 1,
        ownerType: 'course',
        ownerId: 'course.math',
        text: '   ',
        publishedAt: 'tomorrow',
      }),
    ).toThrow()
  })
})
