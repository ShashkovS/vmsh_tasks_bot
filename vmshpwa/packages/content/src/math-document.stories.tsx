import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, fireEvent, userEvent, waitFor, within } from 'storybook/test'

import { webContentDocumentSchema, type WebContentDocument } from '@vmsh/contracts'

import { MathDocument, MathHtml, SemanticMathDocument } from './index'

const sampleHtml = `
  <p><strong>Задача 21н.6.</strong> Найдите все натуральные числа $n$, при которых число
  $n^2 + 179$ является полным квадратом.</p>

  <div class="vmsh-eq" id="eq-nk">
    <div>\\[ n^2 + 179 = k^2, \\qquad k \\in \\mathbb{N}. \\]</div>
    <span class="vmsh-eqno">(1)</span>
  </div>

  <p>Из&nbsp;(<a href="#eq-nk">1</a>) следует $\\left(k-n\\right)\\left(k+n\\right) = 179$, а&nbsp;179 —
  простое число.</p>

  <aside class="vmsh-note">
    <span class="vmsh-note-title">Наблюдение.</span> Числа $k-n$ и $k+n$ имеют одинаковую
    чётность, поэтому оба нечётны.
  </aside>

  <ol>
    <li>Объясните, почему $k - n = 1$, а $k + n = 179$.</li>
    <li>Найдите $n$ и проверьте ответ подстановкой в&nbsp;(1).</li>
  </ol>

  <table>
    <thead>
      <tr><th scope="col">k − n</th><th scope="col">k + n</th><th scope="col">k</th><th scope="col">n</th><th scope="col">Подходит?</th></tr>
    </thead>
    <tbody>
      <tr><td>$1$</td><td>$179$</td><td>$90$</td><td>$89$</td><td>да, $89^2 + 179 = 90^2$</td></tr>
      <tr><td>$179$</td><td>$1$</td><td>$90$</td><td>$-89$</td><td>нет, $n$ не натуральное</td></tr>
    </tbody>
  </table>
`

const sourceSha256 = '53a5d2ba55853ef588a45fb41ce1f1e02b094dc64cf6f7fb476354729d22e05f'
const figureSha256 = '2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae'

const semanticDocument = webContentDocumentSchema.parse({
  contractVersion: 1,
  revisionId: 'revision:lesson-41-n-condition-v3',
  sourceSha256,
  materialKind: 'condition',
  title: 'Листок для начинающих',
  introduction: [
    {
      type: 'paragraph',
      children: [
        { type: 'text', value: 'В каждой задаче важно объяснить ход рассуждения. ' },
        {
          type: 'link',
          href: '#problem-1',
          children: [{ type: 'text', value: 'Начните с первой задачи.' }],
        },
      ],
    },
    {
      type: 'callout',
      kind: 'note',
      title: 'Обозначения.',
      blocks: [
        {
          type: 'paragraph',
          children: [
            { type: 'text', value: 'Буквой ' },
            { type: 'math', latex: '\\mathbb{N}' },
            { type: 'text', value: ' обозначены натуральные числа.' },
          ],
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
          children: [
            { type: 'text', value: 'Последний срок сдачи — после занятия; сохраните ' },
            { type: 'math', latex: 'n^2 + 179 = k^2' },
            { type: 'text', value: ' в решении.' },
          ],
        },
      ],
    },
  ],
  problems: [
    {
      ordinal: 1,
      sourceItem: '41н.1',
      title: 'Загаданное число',
      blocks: [
        {
          type: 'paragraph',
          children: [
            { type: 'text', value: 'Найдите натуральное ' },
            { type: 'math', latex: 'n' },
            { type: 'text', value: ', если ' },
            { type: 'math', latex: 'n^2 + 179 = k^2' },
            { type: 'text', value: '.' },
          ],
        },
        { type: 'formula', latex: '(k-n)(k+n)=179', anchor: 'eq-factor', label: '(1)' },
        {
          type: 'list',
          ordered: true,
          items: [
            [
              {
                type: 'subpart',
                label: 'а)',
                blocks: [
                  {
                    type: 'paragraph',
                    children: [{ type: 'text', value: 'Перечислите разложения 179.' }],
                  },
                ],
              },
            ],
            [
              {
                type: 'paragraph',
                children: [{ type: 'text', value: 'Проверьте найденное значение.' }],
              },
            ],
          ],
        },
        {
          type: 'table',
          caption: [{ type: 'text', value: 'Возможные разложения' }],
          rows: [
            [
              { type: 'header', scope: 'col', children: [{ type: 'text', value: 'k−n' }] },
              { type: 'header', scope: 'col', children: [{ type: 'text', value: 'k+n' }] },
              { type: 'header', scope: 'col', children: [{ type: 'text', value: 'Вывод' }] },
            ],
            [
              { type: 'data', children: [{ type: 'math', latex: '1' }] },
              { type: 'data', children: [{ type: 'math', latex: '179' }] },
              { type: 'data', children: [{ type: 'math', latex: 'n=89' }] },
            ],
          ],
        },
        {
          type: 'figure',
          alt: 'Две пересекающиеся окружности с отмеченными точками A, B и O',
          caption: [{ type: 'text', value: 'Рис. 1. Вспомогательная схема.' }],
          asset: {
            status: 'available',
            assetId: 'asset:geometry-1',
            contentSha256: figureSha256,
            src: '/content/geometry.svg',
            mediaType: 'image/svg+xml',
            width: 800,
            height: 480,
          },
        },
      ],
    },
  ],
})

const missingAssetDocument = webContentDocumentSchema.parse({
  ...semanticDocument,
  revisionId: 'revision:lesson-41-n-missing-preview',
  problems: [
    {
      ...semanticDocument.problems[0],
      blocks: [
        {
          type: 'figure',
          alt: 'Чертёж к задаче о двух окружностях',
          caption: [{ type: 'text', value: 'Рис. 1. Чертёж будет добавлен администратором.' }],
          asset: { status: 'missing', logicalName: 'two-circles.tikz' },
        },
      ],
    },
  ],
})

function buildLongDocument(): WebContentDocument {
  return webContentDocumentSchema.parse({
    ...semanticDocument,
    revisionId: 'revision:lesson-41-n-long-sheet',
    title: 'Длинный листок · 36 задач',
    problems: Array.from({ length: 36 }, (_, index) => ({
      ordinal: index + 1,
      sourceItem: `41н.${index + 1}`,
      title: `Задача ${index + 1}`,
      blocks: [
        {
          type: 'paragraph',
          children: [
            { type: 'text', value: 'Докажите, что для натурального ' },
            { type: 'math', latex: `n_${index + 1}` },
            { type: 'text', value: ' выполняется равенство ' },
            { type: 'math', latex: `1+2+\\dots+n_${index + 1}=\\frac{n(n+1)}2` },
            { type: 'text', value: '.' },
          ],
        },
      ],
    })),
  })
}

function DocumentCanvas({ document = semanticDocument }: { document?: WebContentDocument }) {
  return (
    <SemanticMathDocument
      className="mx-auto max-w-3xl rounded-lg border bg-card p-6"
      document={document}
    />
  )
}

const meta = {
  title: 'Product/Mathematical document',
  component: DocumentCanvas,
  parameters: { layout: 'padded' },
} satisfies Meta<typeof DocumentCanvas>

export default meta
type Story = StoryObj<typeof meta>

export const SemanticDocument: Story = {
  name: 'Semantic web document',
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await waitFor(() => expect(canvasElement.querySelectorAll('.katex').length).toBeGreaterThan(4))
    await expect(canvas.getByRole('table', { name: 'Возможные разложения' })).toBeVisible()
    await expect(canvas.getByAltText(/Две пересекающиеся окружности/u)).toBeVisible()
    await expect(canvas.getByText('Важно')).toBeVisible()
    await expect(canvas.getByText(/Последний срок сдачи/u)).toBeVisible()
  },
}

export const ClientKaTeX: Story = {
  name: 'Safe legacy HTML + client KaTeX',
  render: () => (
    <MathDocument
      title="Листок для продолжающих"
      className="mx-auto max-w-3xl rounded-lg border bg-card p-6"
    >
      <MathHtml html={sampleHtml} />
    </MathDocument>
  ),
  play: async ({ canvasElement }) => {
    await waitFor(() => expect(canvasElement.querySelectorAll('.katex').length).toBeGreaterThan(1))
    await expect(canvasElement.querySelector('.vmsh-scroll-x > table')).not.toBeNull()
  },
}

export const LongSheet: Story = {
  args: { document: buildLongDocument() },
  play: async ({ canvasElement }) => {
    await waitFor(() => expect(canvasElement.querySelectorAll('.katex').length).toBeGreaterThan(60))
    await expect(within(canvasElement).getByText('41н.36')).toBeVisible()
  },
}

export const ResponsiveTable: Story = {
  render: () => {
    const tableDocument = webContentDocumentSchema.parse({
      ...semanticDocument,
      revisionId: 'revision:wide-table-preview',
      introduction: [],
      problems: [
        {
          ordinal: 1,
          sourceItem: '41н.1',
          title: 'Таблица остатков',
          blocks: [
            {
              type: 'table',
              caption: [{ type: 'text', value: 'Остатки степеней по двенадцати модулям' }],
              rows: [
                Array.from({ length: 12 }, (_, index) => ({
                  type: 'header' as const,
                  scope: 'col' as const,
                  children: [{ type: 'text' as const, value: `Модуль ${index + 2}` }],
                })),
                Array.from({ length: 12 }, (_, index) => ({
                  type: 'data' as const,
                  children: [
                    { type: 'math' as const, latex: `n^{${index + 2}} \\bmod ${index + 2}` },
                  ],
                })),
              ],
            },
          ],
        },
      ],
    })
    return <DocumentCanvas document={tableDocument} />
  },
  play: async ({ canvasElement }) => {
    const table = within(canvasElement).getByRole('table', {
      name: 'Остатки степеней по двенадцати модулям',
    })
    const scroller = table.parentElement
    await expect(scroller).not.toBeNull()
    await expect(scroller?.classList.contains('vmsh-scroll-x')).toBe(true)
    await expect(scroller?.scrollWidth).toBeGreaterThan(scroller?.clientWidth ?? 0)
  },
}

export const UnsafeHtmlRejected: Story = {
  name: 'Malformed or unsafe HTML rejected',
  render: () => (
    <MathDocument title="Небезопасная производная">
      <MathHtml html={'<script>alert(1)</script><p>Этот остаток не должен появиться.</p>'} />
    </MathDocument>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(await canvas.findByRole('alert')).toHaveTextContent('не прошёл проверку')
    await expect(canvas.queryByText('Этот остаток не должен появиться.')).toBeNull()
  },
}

export const InvalidFormula: Story = {
  render: () => {
    const invalid = webContentDocumentSchema.parse({
      ...semanticDocument,
      revisionId: 'revision:invalid-formula-preview',
      introduction: [],
      problems: [
        {
          ordinal: 1,
          sourceItem: '41н.1',
          title: 'Повреждённая формула',
          blocks: [{ type: 'formula', latex: '\\frac{1}{', label: '(1)' }],
        },
      ],
    })
    return <DocumentCanvas document={invalid} />
  },
  play: async ({ canvasElement }) => {
    await expect(await within(canvasElement).findByRole('status')).toHaveTextContent(
      'Формулу не удалось отобразить',
    )
    await expect(within(canvasElement).getByText('41н.1')).toBeVisible()
  },
}

export const MissingAsset: Story = {
  args: { document: missingAssetDocument },
  play: async ({ canvasElement }) => {
    const status = within(canvasElement).getByRole('status')
    await expect(status).toHaveTextContent('Рисунок пока недоступен')
    await expect(status).toHaveTextContent('Чертёж к задаче')
  },
}

export const ZoomCanvas: Story = {
  name: 'Zoom canvas: keyboard and pinch',
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const viewport = canvas.getByRole('region', { name: /Просмотр рисунка/u })
    const transformedCanvas = canvas.getByTestId('figure-canvas')
    const zoom = canvas.getByTestId('figure-zoom')

    await userEvent.click(viewport)
    await userEvent.keyboard('+')
    await expect(zoom).toHaveTextContent('150%')
    await expect(transformedCanvas.style.transform).toContain('scale(1.5)')

    await userEvent.keyboard('0')
    await expect(zoom).toHaveTextContent('100%')

    await fireEvent.pointerDown(viewport, { pointerId: 1, clientX: 100, clientY: 100 })
    await fireEvent.pointerDown(viewport, { pointerId: 2, clientX: 200, clientY: 100 })
    await fireEvent.pointerMove(viewport, { pointerId: 2, clientX: 260, clientY: 100 })
    await waitFor(() => expect(zoom).toHaveTextContent('160%'))
    await expect(transformedCanvas.style.transform).toContain('scale(1.6)')
    await fireEvent.pointerUp(viewport, { pointerId: 1 })
    await fireEvent.pointerUp(viewport, { pointerId: 2 })
  },
}

export const DarkTheme: Story = {
  globals: { theme: 'dark' },
}

export const AnnouncementMobile: Story = {
  name: 'Announcements · mobile',
  parameters: { viewport: { defaultViewport: 'mobile2' } },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByText('Важно')).toBeVisible()
    await expect(canvas.getByText(/Последний срок сдачи/u)).toBeVisible()
  },
}
