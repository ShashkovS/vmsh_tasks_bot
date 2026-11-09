import { describe, expect, it } from 'vitest'

import { parseTelegramMarkdown } from './telegram-markdown'

describe('parseTelegramMarkdown', () => {
  it('projects supported Telegram-style inline formatting', () => {
    expect(parseTelegramMarkdown('**Важно**: _сегодня_ и [ссылка](https://example.org)')).toEqual({
      kind: 'text',
      text: 'Важно: сегодня и ссылка',
      entities: [
        { type: 'bold', offset: 0, length: 5 },
        { type: 'italic', offset: 7, length: 7 },
        { type: 'link', href: 'https://example.org', offset: 17, length: 6 },
      ],
    })
  })
})
