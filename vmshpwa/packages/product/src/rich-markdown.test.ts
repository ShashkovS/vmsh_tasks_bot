import { describe, expect, it } from 'vitest'

import { parseRichMarkdown } from './rich-markdown'

describe('RichDocument Markdown parser', () => {
  it('normalizes the supported Telegram-style subset into recursive AST', () => {
    expect(
      parseRichMarkdown(`## Example Nested Syntax Report for _Q1_
Intro with <u>underlined text</u>, ==marked text==, and $x^2 + y^2$.
**Bold _italic <u>underlined italic bold</u> italic_ bold**

> Quote with **bold**, ~~strike~~, and <tg-spoiler>spoiler</tg-spoiler>.

- List item with \`code\`, <sup>sup</sup>, <sub>sub</sub>, and a footnote[^note]
1. Ordered item
- [ ] Task
- [x] Done

\`\`\`python
print('code')
\`\`\`

---

[^note]: One-line footnote

$$E = mc^2$$`),
    ).toMatchObject({
      schemaVersion: 1,
      media: [],
      blocks: [
        { type: 'heading', level: 2 },
        { type: 'paragraph' },
        { type: 'quote' },
        { type: 'list', ordered: false },
        { type: 'list', ordered: true, start: 1 },
        { type: 'taskList', items: [{ checked: false }, { checked: true }] },
        { type: 'code', language: 'python', code: "print('code')" },
        { type: 'divider' },
        { type: 'footnote', id: 'note' },
        { type: 'math', latex: 'E = mc^2' },
      ],
    })
  })

  it('rejects the explicitly out-of-scope syntax with a position diagnostic', () => {
    expect(() => parseRichMarkdown('###### h6')).toThrow('Заголовок уровня 6')
    expect(() => parseRichMarkdown('| one |\n| --- |\n| two |')).toThrow('Таблицы')
    expect(() => parseRichMarkdown('- parent\n  - child')).toThrow('Вложенные списки')
    expect(() => parseRichMarkdown('[unsafe](http://example.test)')).toThrow('HTTPS')
    expect(() => parseRichMarkdown('$x^2')).toThrow('Незакрытая inline-формула')
  })

  it('keeps a Markdown GIF as a server-copied image rather than a video', () => {
    expect(parseRichMarkdown('![](https://example.com/animation.gif)')).toMatchObject({
      media: [
        {
          mediaId: 'media-1',
          sourceUrl: 'https://example.com/animation.gif',
          mimeType: 'image/gif',
        },
      ],
      blocks: [{ type: 'image', mediaId: 'media-1' }],
    })
  })

  it('preserves the supported Telegram-style inline delimiters and rejects raw HTML', () => {
    const document = parseRichMarkdown(
      '**one** __two__ *three* _four_ ~~five~~ `six` ==seven== ||eight|| [nine](https://t.me/) $x$ <u>ten</u> <sup>11</sup> <sub>12</sub> <tg-spoiler>13</tg-spoiler>',
    )
    const paragraph = document.blocks[0]
    expect(paragraph).toMatchObject({ type: 'paragraph' })
    if (paragraph?.type !== 'paragraph') throw new Error('Expected a paragraph')
    expect(
      paragraph.children.filter((node) => node.type !== 'text').map((node) => node.type),
    ).toEqual([
      'bold',
      'bold',
      'italic',
      'italic',
      'strike',
      'code',
      'mark',
      'spoiler',
      'link',
      'math',
      'underline',
      'sup',
      'sub',
      'spoiler',
    ])
    expect(() => parseRichMarkdown('<script>alert(1)</script>')).toThrow('unsupported html tag')
  })
})
