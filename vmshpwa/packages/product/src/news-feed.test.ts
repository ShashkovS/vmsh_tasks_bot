import { describe, expect, it } from 'vitest'

import feedFixture from '@vmsh/contracts/fixtures/news/feed.v1.json'
import { newsFeedResponseSchema } from '@vmsh/contracts'

import { toTelegramPostView } from './news-feed'
import { toRichTextSegments } from './telegram-post'

describe('news feed projection', () => {
  it('keeps Telegram UTF-16 entity offsets correct after an emoji', () => {
    const post = toTelegramPostView(
      newsFeedResponseSchema.parse(feedFixture).items[0]!,
      (value) => value,
    )
    const block = post.blocks[0]!
    if (block.kind !== 'text') throw new Error('Expected a text block')

    expect(toRichTextSegments(block.text, block.entities ?? [])).toEqual([
      { text: 'A😀' },
      { text: 'Б', entity: { type: 'bold', offset: 3, length: 1 } },
    ])
    expect(post.media?.[0]).toMatchObject({ kind: 'photo' })
  })
})
