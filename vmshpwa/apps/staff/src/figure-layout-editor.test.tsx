import { cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, expect, it, vi } from 'vitest'
import type { ContentApiClient } from '@vmsh/content'
import type { FigureLayout } from '@vmsh/contracts'
import { renderWithI18n as render } from '@vmsh/test-utils/i18n'
import { FigureLayoutEditor } from './figure-layout-editor'

afterEach(cleanup)

it('loads on opening and saves hide/restore using the updated version', async () => {
  const figure = {
    type: 'figure' as const,
    occurrenceId: 'figure-123456789012345678901234',
    alt: 'Схема',
    asset: { status: 'missing' as const, logicalName: 'x.png' },
  }
  const layout: FigureLayout = {
    revisionId: 'revision-layout',
    version: 0,
    entries: [],
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
      problems: [{ ordinal: 1, sourceItem: '1', title: 'Схема', partLabels: [], blocks: [figure] }],
    },
  }
  const load = vi.fn(() => Promise.resolve(layout))
  const save = vi.fn((_id: string, version: number, entries: FigureLayout['entries']) =>
    Promise.resolve({
      ...layout,
      version: version + 1,
      entries,
    }),
  )
  const client = { figureLayout: load, saveFigureLayout: save } as unknown as ContentApiClient
  const preview = vi.fn()
  const user = userEvent.setup()
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <FigureLayoutEditor client={client} revisionId={layout.revisionId} onPreview={preview} />
    </QueryClientProvider>,
  )
  expect(load).not.toHaveBeenCalled()
  await user.click(screen.getByText('Расположение рисунков'))
  await user.click(await screen.findByRole('button', { name: 'Скрыть' }))
  await waitFor(() =>
    expect(save).toHaveBeenCalledWith('revision-layout', 0, [
      expect.objectContaining({ hidden: true, occurrenceId: figure.occurrenceId }),
    ]),
  )
  await user.click(await screen.findByRole('button', { name: 'Восстановить' }))
  await waitFor(() => expect(save).toHaveBeenLastCalledWith('revision-layout', 1, []))
  expect(preview).toHaveBeenCalledTimes(2)
})
