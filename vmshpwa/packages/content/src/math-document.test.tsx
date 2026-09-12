import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import webDocumentFixture from '@vmsh/contracts/fixtures/content/web-document.v1.json'
import { webContentContractFixtureSchema, webContentDocumentSchema } from '@vmsh/contracts'

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
  it('renders full task references without changing subpart identity', () => {
    const document = webContentContractFixtureSchema.parse(webDocumentFixture).document
    render(
      <SemanticMathDocument
        document={{
          ...document,
          introduction: [],
          problems: [
            {
              ...document.problems[0]!,
              taskReference: '1н.11',
              title: 'Никто никого не бьёт',
              blocks: [
                {
                  type: 'subpart',
                  label: 'а',
                  taskReference: '1н.11а',
                  title: 'Первый пункт',
                  blocks: [{ type: 'paragraph', children: [{ type: 'text', value: 'Условие' }] }],
                },
              ],
            },
          ],
        }}
      />,
    )
    expect(
      screen.getByRole('heading', { name: 'Задача 1н.11. «Никто никого не бьёт»' }),
    ).not.toBeNull()
    expect(screen.getByText('Задача 1н.11а.', { exact: false })).not.toBeNull()
  })

  it('renders a runtime-validated semantic document with KaTeX and a responsive table', async () => {
    const contentDocument = webContentContractFixtureSchema.parse(webDocumentFixture).document
    render(<SemanticMathDocument document={contentDocument} />)

    expect(screen.getByRole('heading', { name: /41н\.1 «Загаданное число»/u })).not.toBeNull()
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
    expect(
      screen
        .getByText('Задача')
        .closest('.vmsh-math-content')
        ?.classList.contains('vmsh-telegram-preview'),
    ).toBe(true)
  })

  it('renders a validated subpart name beside its label, retaining old unnamed documents', () => {
    const document = webContentContractFixtureSchema.parse(webDocumentFixture).document
    render(
      <SemanticMathDocument
        document={webContentDocumentSchema.parse({
          ...document,
          introduction: [
            {
              type: 'subpart',
              label: 'а',
              title: 'Два квадрата',
              blocks: [{ type: 'paragraph', children: [{ type: 'text', value: 'Первый пункт' }] }],
            },
          ],
          problems: [],
        })}
      />,
    )

    expect(screen.getByText('«Два квадрата»').closest('strong')?.textContent).toBe(
      'а) «Два квадрата»',
    )
  })

  it('keeps the normalized TeX width and source-side float on a figure', () => {
    const document = webContentContractFixtureSchema.parse(webDocumentFixture).document
    const { container } = render(
      <SemanticMathDocument
        document={{
          ...document,
          introduction: [
            {
              type: 'figure',
              alt: 'Схема справа',
              floatHint: 'right',
              widthHint: '27.778%',
              asset: {
                status: 'available',
                assetId: 'asset:source-sized-figure',
                contentSha256: '2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae',
                src: '/content/source-sized.svg',
                mediaType: 'image/svg+xml',
                width: 800,
                height: 480,
              },
            },
          ],
          problems: [],
        }}
      />,
    )

    const figure = container.querySelector<HTMLElement>('.vmsh-asset-figure')
    expect(figure?.dataset.floatHint).toBe('right')
    expect(figure?.style.getPropertyValue('--vmsh-source-width')).toBe('27.778%')
  })

  it('puts task and subpart actions into their semantic headings', () => {
    const document = webContentContractFixtureSchema.parse(webDocumentFixture).document
    const firstProblem = document.problems[0]
    if (!firstProblem) throw new Error('Fixture must contain a problem')

    render(
      <SemanticMathDocument
        document={{
          ...document,
          introduction: [],
          problems: [
            {
              ...firstProblem,
              blocks: [
                {
                  type: 'subpart',
                  label: 'а',
                  blocks: [
                    { type: 'paragraph', children: [{ type: 'text', value: 'Первый пункт' }] },
                  ],
                },
              ],
            },
          ],
        }}
        renderProblemActions={() => <button type="button">Открыть задачу</button>}
        renderSubpartActions={() => <button type="button">Открыть пункт</button>}
      />,
    )

    expect(screen.getByRole('button', { name: 'Открыть задачу' }).parentElement?.className).toBe(
      'vmsh-problem-header',
    )
    expect(screen.getByRole('button', { name: 'Открыть пункт' }).parentElement?.className).toBe(
      'vmsh-subpart-header',
    )
  })

  it('renders problem controls before content between adjacent problems', () => {
    const document = webContentContractFixtureSchema.parse(webDocumentFixture).document
    const firstProblem = document.problems[0]
    if (!firstProblem) throw new Error('Fixture must contain a problem')

    const { container } = render(
      <SemanticMathDocument
        document={{
          ...document,
          introduction: [],
          problems: [
            {
              ...firstProblem,
              trailingBlocks: [
                {
                  type: 'heading',
                  level: 2,
                  children: [{ type: 'text', value: 'Общий комментарий' }],
                },
              ],
            },
          ],
        }}
        renderAfterProblem={() => <button type="button">Ответить</button>}
      />,
    )

    const button = screen.getByRole('button', { name: 'Ответить' })
    const commentary = screen.getByRole('heading', { name: 'Общий комментарий' })
    expect(button.compareDocumentPosition(commentary) & Node.DOCUMENT_POSITION_FOLLOWING).not.toBe(
      0,
    )
    expect(container.querySelector('.vmsh-problem')?.contains(commentary)).toBe(false)
  })

  it('renders a task preamble before the task heading', () => {
    const document = webContentContractFixtureSchema.parse(webDocumentFixture).document
    const firstProblem = document.problems[0]
    if (!firstProblem) throw new Error('Fixture must contain a problem')

    const { container } = render(
      <SemanticMathDocument
        document={{
          ...document,
          introduction: [],
          problems: [
            {
              ...firstProblem,
              preambleBlocks: [
                {
                  type: 'paragraph',
                  children: [{ type: 'text', value: 'Теория перед задачей.' }],
                },
              ],
            },
          ],
        }}
      />,
    )

    const section = container.querySelector('.vmsh-problem')
    const preamble = screen.getByText('Теория перед задачей.')
    const taskHeading = section?.querySelector('h2')
    expect(taskHeading).not.toBeNull()
    expect(
      preamble.compareDocumentPosition(taskHeading!) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).not.toBe(0)
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

  it('cycles a Student figure locally without rendering zoom controls', () => {
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

    const canvas = screen.getByTestId('figure-canvas')
    expect(canvas.closest('figure')?.style.getPropertyValue('--vmsh-figure-scale')).toBe('1')
    fireEvent.click(canvas)
    expect(canvas.closest('figure')?.style.getPropertyValue('--vmsh-figure-scale')).toBe('1.25')
    expect(screen.queryByRole('group', { name: 'Масштаб рисунка' })).toBeNull()
  })

  it('sends the next persisted Staff scale on a figure click', () => {
    const scales: number[] = []
    render(
      <ZoomableAssetFigure
        alt="Схема для Staff"
        asset={{
          status: 'available',
          assetId: 'asset:staff-figure',
          contentSha256: '2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae',
          src: '/content/staff-geometry.svg',
          mediaType: 'image/svg+xml',
          width: 800,
          height: 480,
        }}
        onScaleCycle={(scale) => scales.push(scale)}
        scale={1.5}
      />,
    )

    fireEvent.click(screen.getByTestId('figure-canvas'))
    expect(scales).toEqual([1.75])
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
