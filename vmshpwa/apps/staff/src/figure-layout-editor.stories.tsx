import { useState } from 'react'
import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, userEvent, waitFor, within } from 'storybook/test'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SemanticMathDocument, type ContentApiClient } from '@vmsh/content'
import {
  webContentContractFixtureSchema,
  type FigureLayout,
  type WebContentBlock,
  type WebContentDocument,
} from '@vmsh/contracts'
import fixture from '@vmsh/contracts/fixtures/content/web-document.v1.json'
import { FigureLayoutEditor } from './figure-layout-editor'

const parsed = webContentContractFixtureSchema.parse(fixture).document
const sourceFigure = parsed.problems.flatMap((p) => p.blocks).find((b) => b.type === 'figure')!
const figure = {
  ...sourceFigure,
  occurrenceId: 'figure-123456789012345678901234',
  alt: 'Схема',
  asset: {
    status: 'available' as const,
    assetId: 'ma-story',
    contentSha256: 'a'.repeat(64),
    src: '/content/geometry.svg',
    mediaType: 'image/svg+xml' as const,
    width: 800,
    height: 600,
  },
}
const baseDocument: WebContentDocument = {
  ...parsed,
  materialKind: 'condition',
  introduction: [],
  problems: [
    {
      ordinal: 1,
      sourceItem: '1',
      title: null,
      partLabels: [],
      blocks: [
        {
          type: 'paragraph',
          children: [{ type: 'text', value: 'Объясните, как найти площадь фигуры.' }],
        },
        figure,
        {
          type: 'paragraph',
          children: [{ type: 'text', value: 'Запишите решение и проверьте ответ.' }],
        },
      ],
    },
  ],
}

/** Story-only API boundary; production implementation is docs/figure-layout.md. */
function EditorPreview({ conflict = false, tiny = false }: { conflict?: boolean; tiny?: boolean }) {
  const sourceDocument: WebContentDocument = tiny
    ? {
        ...baseDocument,
        problems: baseDocument.problems.map((p) => ({
          ...p,
          blocks: p.blocks.map((b) => (b.type === 'figure' ? { ...b, widthHint: '32px' } : b)),
        })),
      }
    : baseDocument
  const [document, setDocument] = useState(sourceDocument)
  const [queryClient] = useState(
    () => new QueryClient({ defaultOptions: { queries: { retry: false } } }),
  )
  const [client] = useState(() => {
    const initial: FigureLayout = {
      revisionId: sourceDocument.revisionId,
      version: 0,
      entries: [],
      hasUnpublishedChanges: false,
      canPublish: true,
      figures: [
        {
          occurrenceId: figure.occurrenceId,
          sourceOrdinal: 1,
          sourcePart: null,
          sourceSection: 'common',
          figure: tiny ? { ...figure, widthHint: '32px' } : figure,
        },
      ],
      document: sourceDocument,
    }
    const api: Pick<ContentApiClient, 'figureLayout' | 'saveFigureLayout'> = {
      figureLayout: () => Promise.resolve(initial),
      saveFigureLayout: (_revision, version, entries) => {
        if (conflict) return Promise.reject(new Error('Simulated save failure'))
        const entry = entries[0]
        const blocks = sourceDocument.problems[0]!.blocks.flatMap<WebContentBlock>((b) => {
          if (b.type !== 'figure') return [b]
          return entry?.hidden
            ? []
            : [{ ...b, widthRem: entry?.widthRem, placement: entry?.placement }]
        })
        return Promise.resolve({
          ...initial,
          version: version + 1,
          entries,
          hasUnpublishedChanges: entries.length > 0,
          document: { ...sourceDocument, problems: [{ ...sourceDocument.problems[0]!, blocks }] },
        })
      },
    }
    return api as ContentApiClient
  })
  return (
    <QueryClientProvider client={queryClient}>
      <FigureLayoutEditor
        client={client}
        revisionId={sourceDocument.revisionId}
        onPreview={setDocument}
      >
        {(tools) => <SemanticMathDocument document={document} renderFigureTools={tools} />}
      </FigureLayoutEditor>
    </QueryClientProvider>
  )
}
const meta = { title: 'Pages/Staff/Inline figure editor', component: EditorPreview } satisfies Meta<
  typeof EditorPreview
>
export default meta
type Story = StoryObj<typeof meta>
export const WidthAndPlacement: Story = {
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const popup = within(canvasElement.ownerDocument.body)
    await userEvent.click(await canvas.findByRole('button', { name: 'Размер и размещение: Схема' }))
    const input = popup.getByRole('spinbutton', { name: 'Ширина, rem' })
    await userEvent.clear(input)
    await userEvent.type(input, '12')
    await userEvent.tab()
    await waitFor(() =>
      expect(canvas.getByTestId('asset-figure').style.getPropertyValue('--vmsh-source-width')).toBe(
        '12rem',
      ),
    )
    await userEvent.selectOptions(popup.getByLabelText('Размещение'), 'center-source')
    await waitFor(() =>
      expect(canvas.getByTestId('asset-figure')).toHaveAttribute('data-placement', 'center-source'),
    )
    await userEvent.keyboard('{Escape}')
    await waitFor(() => expect(popup.queryByRole('dialog', { hidden: true })).toBeNull())
  },
}
export const SaveFailure: Story = {
  args: { conflict: true },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const popup = within(canvasElement.ownerDocument.body)
    await userEvent.click(await canvas.findByRole('button', { name: 'Размер и размещение: Схема' }))
    await userEvent.click(popup.getByRole('button', { name: 'Уменьшить ширину' }))
    await userEvent.keyboard('{Escape}')
    await waitFor(() => expect(popup.queryByRole('dialog', { hidden: true })).toBeNull())
    await expect(await canvas.findByRole('alert')).toBeVisible()
    await expect(canvas.getByRole('button', { name: 'Обновить' })).toBeEnabled()
  },
}
export const TinySourceFigure: Story = {
  args: { tiny: true },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const popup = within(canvasElement.ownerDocument.body)
    const element = canvas.getByTestId('asset-figure')
    await waitFor(() => expect(element).toHaveAttribute('data-editor-small', 'true'))
    const image = element.querySelector('img')!
    const button = canvas.getByRole('button', { name: 'Размер и размещение: Схема' })
    await expect(button.getBoundingClientRect().top).toBeGreaterThanOrEqual(
      image.getBoundingClientRect().bottom,
    )
    await userEvent.click(button)
    await expect(popup.getByRole('spinbutton', { name: 'Ширина, rem' })).toHaveValue(2)
    await userEvent.keyboard('{Escape}')
    await waitFor(() => expect(popup.queryByRole('dialog', { hidden: true })).toBeNull())
    await expect(element).not.toHaveAttribute('data-placement')
    await expect(element.style.getPropertyValue('--vmsh-source-width')).toBe('32px')
  },
}
