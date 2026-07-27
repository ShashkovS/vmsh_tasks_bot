import { describe, expect, it } from 'vitest'

import { sanitizeSemanticHtml } from './sanitizer'

function sanitizedContainer(html: string): HTMLDivElement {
  const result = sanitizeSemanticHtml(html)
  expect(result.ok).toBe(true)
  if (!result.ok) throw new Error('Expected sanitizer success')
  const container = document.createElement('div')
  container.append(result.fragment)
  return container
}

describe('semantic HTML sanitizer', () => {
  it('keeps only the explicit educational HTML dialect and safe URLs', () => {
    const container = sanitizedContainer(`
      <h2 id="problem-1">Задача</h2>
      <p><strong>Докажите</strong> утверждение <a href="https://example.test/note">по заметке</a>.</p>
      <aside class="vmsh-note"><span class="vmsh-note-title">Наблюдение.</span> Текст.</aside>
      <img src="/student/api/v1/content/assets/figure-1" alt="Схема" width="800" height="480">
    `)

    expect(container.querySelector('#problem-1')).not.toBeNull()
    expect(container.querySelector('a')?.getAttribute('href')).toBe('https://example.test/note')
    expect(container.querySelector('img')?.getAttribute('alt')).toBe('Схема')
  })

  it.each([
    '<p onclick="alert(1)">Текст</p>',
    '<p style="color:red">Текст</p>',
    '<script>alert(1)</script><p>Безопасный остаток</p>',
    '<form><input name="answer"></form>',
    '<svg><script>alert(1)</script></svg>',
    '<a href="javascript:alert(1)">ссылка</a>',
    '<img src="data:image/svg+xml,<svg/>" alt="Схема">',
    '<aside class="arbitrary-product-color">Текст</aside>',
  ])('fails the whole derivative closed for unsupported markup: %s', (html) => {
    expect(sanitizeSemanticHtml(html)).toEqual({ ok: false, reason: 'unsupported-markup' })
  })

  it('rejects an oversized derivative before parsing it', () => {
    expect(sanitizeSemanticHtml('x'.repeat(1_000_001))).toEqual({
      ok: false,
      reason: 'too-large',
    })
  })
})
