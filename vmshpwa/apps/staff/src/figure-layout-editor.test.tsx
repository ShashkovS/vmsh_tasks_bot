import { cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, expect, it, vi } from 'vitest'
import { SemanticMathDocument, type ContentApiClient } from '@vmsh/content'
import type { FigureLayout } from '@vmsh/contracts'
import { renderWithI18n as render } from '@vmsh/test-utils/i18n'
import { FigureLayoutEditor } from './figure-layout-editor'

afterEach(cleanup)

function setup() {
  const figure = {
    type: 'figure' as const,
    occurrenceId: 'figure-123456789012345678901234',
    alt: 'Схема',
    asset: {
      status: 'available' as const,
      assetId: 'ma-1',
      contentSha256: 'a'.repeat(64),
      src: '/media/scheme.svg',
      mediaType: 'image/svg+xml' as const,
      width: 800,
      height: 1200,
    },
  }
  const layout: FigureLayout = {
    revisionId: 'revision-layout',
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
        figure,
      },
    ],
    document: {
      contractVersion: 1,
      sourceSha256: 'a'.repeat(64),
      revisionId: 'revision-layout',
      materialKind: 'condition',
      title: null,
      introduction: [],
      problems: [
        { ordinal: 1, sourceItem: '1', title: 'Схема', partLabels: ['а'], blocks: [figure] },
        {
          ordinal: 2,
          sourceItem: '2',
          title: 'Соседняя задача',
          partLabels: [],
          blocks: [{ type: 'paragraph', children: [{ type: 'text', value: 'Текст' }] }],
        },
      ],
    },
  }
  const load = vi.fn(() => Promise.resolve(layout))
  const save = vi.fn((_id: string, version: number, entries: FigureLayout['entries']) =>
    Promise.resolve({
      ...layout,
      version: version + 1,
      entries,
      hasUnpublishedChanges: entries.length > 0,
    }),
  )
  const client = { figureLayout: load, saveFigureLayout: save } as unknown as ContentApiClient
  const preview = vi.fn()
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <FigureLayoutEditor client={client} revisionId={layout.revisionId} onPreview={preview}>
        {(tools) => <SemanticMathDocument document={layout.document} renderFigureTools={tools} />}
      </FigureLayoutEditor>
    </QueryClientProvider>,
  )
  return { user: userEvent.setup(), save, preview }
}

it('edits width in place and saves one occurrence with the current draft version', async () => {
  const { user, save, preview } = setup()
  await user.click(await screen.findByRole('button', { name: 'Размер и размещение: Схема' }))
  const input = screen.getByRole('spinbutton', { name: 'Ширина, rem' })
  await user.clear(input)
  await user.type(input, '12')
  expect(preview).toHaveBeenCalledWith(
    expect.objectContaining({
      problems: expect.arrayContaining([
        expect.objectContaining({ blocks: [expect.objectContaining({ widthRem: 12 })] }),
      ]),
    }),
  )
  expect(save).not.toHaveBeenCalled()
  await user.tab()
  await waitFor(() =>
    expect(save).toHaveBeenCalledWith('revision-layout', 0, [
      expect.objectContaining({ widthRem: 12, placement: 'source', targetOrdinal: 1 }),
    ]),
  )
  await waitFor(() => expect(screen.getByLabelText('Размещение').matches(':disabled')).toBe(false))
  await user.selectOptions(screen.getByLabelText('Размещение'), 'center-after')
  await waitFor(() =>
    expect(save).toHaveBeenLastCalledWith('revision-layout', 1, [
      expect.objectContaining({ widthRem: 12, placement: 'center-after' }),
    ]),
  )
})

it('moves to the next task and hides/restores without losing its destination', async () => {
  const { user, save } = setup()
  await user.click(await screen.findByRole('button', { name: 'Действия с рисунком: Схема' }))
  expect(screen.getByRole('button', { name: 'В предыдущую задачу' }).matches(':disabled')).toBe(
    true,
  )
  await user.click(screen.getByRole('button', { name: 'В следующую задачу' }))
  await waitFor(() =>
    expect(save).toHaveBeenCalledWith('revision-layout', 0, [
      expect.objectContaining({ targetOrdinal: 2, targetPart: null, placement: 'center-after' }),
    ]),
  )
  await waitFor(() =>
    expect(screen.getByRole('button', { name: 'Скрыть рисунок' }).matches(':disabled')).toBe(false),
  )
  await user.click(screen.getByRole('button', { name: 'Скрыть рисунок' }))
  await user.click(await screen.findByRole('button', { name: 'Восстановить' }))
  await waitFor(() =>
    expect(save).toHaveBeenLastCalledWith('revision-layout', 2, [
      expect.objectContaining({ targetOrdinal: 2, placement: 'center-after', hidden: false }),
    ]),
  )
})

it('can move a figure from its position in the text to a specific part', async () => {
  const { user, save } = setup()
  await user.click(await screen.findByRole('button', { name: 'Размер и размещение: Схема' }))
  await user.selectOptions(screen.getByLabelText('Размещение'), 'center-source')
  await waitFor(() =>
    expect(save).toHaveBeenCalledWith('revision-layout', 0, [
      expect.objectContaining({ placement: 'center-source', targetPart: null }),
    ]),
  )
  expect(save).toHaveBeenCalledTimes(1)
  expect(save.mock.calls[0]![2][0]).not.toHaveProperty('widthRem')
  await user.keyboard('{Escape}')
  await user.click(await screen.findByRole('button', { name: 'Действия с рисунком: Схема' }))
  await user.click(screen.getByText('Дополнительные настройки'))
  await user.selectOptions(screen.getByLabelText('Пункт'), 'а')
  await waitFor(() =>
    expect(save).toHaveBeenLastCalledWith('revision-layout', 1, [
      expect.objectContaining({ placement: 'center-before', targetPart: 'а' }),
    ]),
  )
})
