import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import webDocumentFixture from '@vmsh/contracts/fixtures/content/web-document.v1.json'
import { webContentContractFixtureSchema } from '@vmsh/contracts'

import {
  katexRenderLimits,
  MathExpression,
  MathHtml,
  SemanticMathDocument,
  TelegramMathHtml,
  ZoomableAssetFigure,
} from './index'

afterEach(() => cleanup())

describe('browser math content renderer', () => {
  it('renders a runtime-validated semantic document with KaTeX and a responsive table', async () => {
    const contentDocument = webContentContractFixtureSchema.parse(webDocumentFixture).document
    render(<SemanticMathDocument document={contentDocument} />)

    expect(screen.getByRole('heading', { name: /41н\.1 Загаданное число/u })).not.toBeNull()
    expect(screen.getByRole('table', { name: 'Возможные разложения' })).not.toBeNull()
    expect(screen.getByRole('table').parentElement?.classList.contains('vmsh-scroll-x')).toBe(true)
    await waitFor(() =>
      expect(globalThis.document.querySelectorAll('.katex').length).toBeGreaterThan(1),
    )
  })

  it('does not render a safe-looking remainder when legacy HTML contains unsafe markup', async () => {
    render(<MathHtml html={'<script>alert(1)</script><p>Безопасный остаток</p>'} />)

    expect(await screen.findByRole('alert')).not.toBeNull()
    expect(screen.queryByText('Безопасный остаток')).toBeNull()
    expect(document.querySelector('script')).toBeNull()
  })

  it('renders the Telegram bold and italic dialect through the safe browser preview', async () => {
    render(
      <TelegramMathHtml html="<h2>Задача</h2><p><b>Важно</b> и <i>курсив</i>: <tg-math>2+2</tg-math></p>" />,
    )

    expect(await screen.findByText('Важно')).not.toBeNull()
    expect(screen.getByText('курсив')).not.toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('adds the visible closing parenthesis to semantic subpart labels', () => {
    const document = webContentContractFixtureSchema.parse(webDocumentFixture).document
    render(
      <SemanticMathDocument
        document={{
          ...document,
          introduction: [
            {
              type: 'subpart',
              label: 'а',
              blocks: [{ type: 'paragraph', children: [{ type: 'text', value: 'Первый пункт' }] }],
            },
          ],
          problems: [],
        }}
      />,
    )

    expect(screen.getByText('а)')).not.toBeNull()
  })

  it('keeps the rest of a document visible when one formula is invalid', async () => {
    render(
      <p>
        Текст до формулы. <MathExpression latex="\\frac{1}{" /> Текст после формулы.
      </p>,
    )

    expect((await screen.findByRole('status')).textContent).toContain(
      'Формулу не удалось отобразить',
    )
    expect(screen.getByText(/Текст до формулы/u)).not.toBeNull()
    expect(screen.getByText(/Текст после формулы/u)).not.toBeNull()
    expect(katexRenderLimits).toEqual({ maxExpand: 1_000, maxSize: 20 })
  })

  it('renders regular and important announcement callouts with distinct semantics', () => {
    const document = webContentContractFixtureSchema.parse(webDocumentFixture).document
    render(
      <SemanticMathDocument
        document={{
          ...document,
          introduction: [
            {
              type: 'callout',
              kind: 'note',
              blocks: [
                {
                  type: 'paragraph',
                  children: [{ type: 'text', value: 'Спокойное объявление' }],
                },
              ],
            },
            {
              type: 'callout',
              kind: 'theorem',
              title: 'Важно',
              blocks: [
                {
                  type: 'paragraph',
                  children: [{ type: 'text', value: 'Важное объявление' }],
                },
              ],
            },
          ],
          problems: [],
        }}
      />,
    )

    const regular = screen.getByText('Спокойное объявление').closest('aside')
    const important = screen.getByText('Важное объявление').closest('aside')
    expect(regular?.classList.contains('vmsh-callout-note')).toBe(true)
    expect(important?.classList.contains('vmsh-callout-theorem')).toBe(true)
    expect(screen.getByText('Важно')).not.toBeNull()
  })

  it('scales the framed canvas with keyboard controls and resets it', () => {
    render(
      <ZoomableAssetFigure
        alt="Синтетическая схема"
        asset={{
          status: 'available',
          assetId: 'asset:test-figure',
          contentSha256: '2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae',
          src: '/content/geometry.svg',
          mediaType: 'image/svg+xml',
          width: 800,
          height: 480,
        }}
        caption="Рис. 1. Синтетическая схема."
      />,
    )

    const viewport = screen.getByTestId('figure-viewport')
    const canvas = screen.getByTestId('figure-canvas')
    fireEvent.keyDown(viewport, { key: '+' })
    expect(screen.getByTestId('figure-zoom').textContent).toContain('150%')
    expect(canvas.style.transform).toContain('scale(1.5)')
    fireEvent.keyDown(viewport, { key: '0' })
    expect(screen.getByTestId('figure-zoom').textContent).toContain('100%')
    expect(canvas.style.transform).toContain('scale(1)')
  })

  it('shows a stable missing-image fallback without dropping the caption', () => {
    render(
      <ZoomableAssetFigure
        alt="Схема, которую не удалось загрузить"
        asset={{
          status: 'available',
          assetId: 'asset:missing-test-figure',
          contentSha256: '2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae',
          src: '/content/missing.svg',
          mediaType: 'image/svg+xml',
          width: 800,
          height: 480,
        }}
        caption="Рис. 2. Подпись остаётся доступной."
      />,
    )

    fireEvent.error(screen.getByAltText('Схема, которую не удалось загрузить'))
    expect(screen.getByText('Рисунок недоступен.')).not.toBeNull()
    expect(screen.getByText('Рис. 2. Подпись остаётся доступной.')).not.toBeNull()
  })
})
