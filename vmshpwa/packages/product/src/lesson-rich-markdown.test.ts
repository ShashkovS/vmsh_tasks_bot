import { describe, expect, it } from 'vitest'

import { parseLessonRichMarkdown } from './lesson-rich-markdown'

describe('lesson rich Markdown', () => {
  it('keeps root videos in their source position', () => {
    const document = parseLessonRichMarkdown(
      'До[^note]\n\n::video[Разбор](https://youtu.be/FTXGKbAk9To?t=90)\n\nПосле\n\n[^note]: Сноска',
    )
    expect(document.blocks.map((block) => block.type)).toEqual([
      'paragraph',
      'video',
      'paragraph',
      'footnote',
    ])
    expect(document.blocks[1]).toMatchObject({ provider: 'youtube', startSeconds: 90 })
  })

  it('parses both supplied provider iframes as safe video nodes', () => {
    const document = parseLessonRichMarkdown(
      '<iframe width="560" height="315" src="https://www.youtube.com/embed/FTXGKbAk9To?si=QlPSxe22wDSyAwcw" title="YouTube video player" frameborder="0" allowfullscreen></iframe>\n\n<iframe src="https://vkvideo.ru/video_ext.php?oid=-241691838&amp;id=456239017&amp;hd=2" width="853" height="480" allowfullscreen></iframe>',
    )
    expect(document.blocks).toMatchObject([
      { type: 'video', provider: 'youtube', videoId: 'FTXGKbAk9To' },
      { type: 'video', provider: 'vk', ownerId: '-241691838', videoId: '456239017' },
    ])
  })

  it('does not turn iframe text in a code fence into a player', () => {
    const document = parseLessonRichMarkdown(
      '```html\n<iframe src="https://www.youtube.com/embed/FTXGKbAk9To"></iframe>\n```',
    )
    expect(document.blocks).toEqual([
      {
        type: 'code',
        language: 'html',
        code: '<iframe src="https://www.youtube.com/embed/FTXGKbAk9To"></iframe>',
      },
    ])
  })

  it.each(['\n', '\n\n', '\r\n'])(
    'accepts an empty-title directive with trailing whitespace %j',
    (ending) => {
      expect(
        parseLessonRichMarkdown('Текст\n\n::video[](https://youtu.be/4ke2IJirSds)' + ending)
          .blocks[1],
      ).toMatchObject({ type: 'video', provider: 'youtube' })
    },
  )

  it('rejects a video nested in a quote or list', () => {
    expect(() => parseLessonRichMarkdown('> ::video[](https://youtu.be/FTXGKbAk9To)')).toThrow(
      'корневым блоком',
    )
  })
})
