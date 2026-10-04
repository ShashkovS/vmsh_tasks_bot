import { useState } from 'react'
import { act, cleanup, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, expect, it, vi } from 'vitest'
import type { ContentApiClient } from '@vmsh/content'
import type { FigureLayout, WebContentDocument } from '@vmsh/contracts'
import { renderWithI18n as render } from '@vmsh/test-utils/i18n'
import { FigureLayoutEditor } from './figure-layout-editor'
import { StaffWorksheetPreview } from './staff-worksheet-preview'

afterEach(cleanup)

// docs/figure-layout.md: tools load after the disclosure mounts, then follow its draft.
it.each(['hint', 'solution'] as const)(
  'edits an open %s after loading tools and keeps neighbouring materials read-only',
  async (kind) => {
    const figure = {
      type: 'figure' as const,
      occurrenceId: 'figure-123456789012345678901234',
      alt: 'Схема материала',
      widthRem: 12,
      asset: {
        status: 'available' as const,
        assetId: 'ma-1',
        contentSha256: 'a'.repeat(64),
        src: '/media/scheme.svg',
        mediaType: 'image/svg+xml' as const,
        width: 800,
        height: 600,
      },
    }
    const source: WebContentDocument = {
      contractVersion: 1,
      sourceSha256: 'a'.repeat(64),
      revisionId: `revision-${kind}`,
      materialKind: kind,
      title: null,
      introduction: [],
      problems: [1, 2].map((ordinal) => ({
        ordinal,
        sourceItem: String(ordinal),
        title: null,
        partLabels: [],
        blocks: ordinal === 1 ? [figure] : [],
      })),
    }
    const condition: WebContentDocument = {
      ...source,
      revisionId: 'revision-condition',
      materialKind: 'condition',
      problems: source.problems.map((problem) => ({
        ...problem,
        // Even a repeated occurrence identity must not expose this revision's tools.
        blocks: problem.ordinal === 1 ? [{ ...figure, alt: 'Схема условия' }] : [],
      })),
    }
    const neighbour: WebContentDocument = {
      ...condition,
      revisionId: 'revision-neighbour',
      materialKind: kind === 'hint' ? 'solution' : 'hint',
      problems: condition.problems.map((problem) => ({
        ...problem,
        blocks: problem.ordinal === 1 ? [{ ...figure, alt: 'Схема соседнего материала' }] : [],
      })),
    }
    const initial: FigureLayout = {
      revisionId: source.revisionId,
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
      document: source,
    }
    let resolveLayout!: (layout: FigureLayout) => void
    const loaded = new Promise<FigureLayout>((resolve) => {
      resolveLayout = resolve
    })
    const save = vi.fn((_id: string, version: number, entries: FigureLayout['entries']) => {
      const entry = entries[0]
      return Promise.resolve({
        ...initial,
        version: version + 1,
        entries,
        document: {
          ...source,
          problems: source.problems.map((problem) => ({
            ...problem,
            blocks:
              !entry?.hidden && problem.ordinal === (entry?.targetOrdinal ?? 1)
                ? [{ ...figure, widthRem: entry?.widthRem ?? 12, placement: entry?.placement }]
                : [],
          })),
        },
      })
    })
    const client = {
      figureLayout: () => loaded,
      saveFigureLayout: save,
    } as unknown as ContentApiClient
    function Preview() {
      const [document, setDocument] = useState(source)
      return (
        <FigureLayoutEditor client={client} revisionId={source.revisionId} onPreview={setDocument}>
          {(tools) => (
            <StaffWorksheetPreview
              condition={condition}
              document={document}
              hintDocument={kind === 'solution' ? neighbour : undefined}
              solutionDocument={kind === 'hint' ? neighbour : undefined}
              renderFigureTools={tools}
              submissionClosed={false}
            />
          )}
        </FigureLayoutEditor>
      )
    }
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={queryClient}>
        <Preview />
      </QueryClientProvider>,
    )
    const user = userEvent.setup()
    expect(screen.getByRole('img', { name: 'Схема материала' })).toBeTruthy()
    expect(
      screen.queryByRole('button', { name: 'Размер и размещение: Схема материала' }),
    ).toBeNull()
    await act(async () => {
      resolveLayout(initial)
      await loaded
    })
    await user.click(
      await screen.findByRole('button', { name: 'Размер и размещение: Схема материала' }),
    )
    expect(screen.queryByRole('button', { name: 'Размер и размещение: Схема условия' })).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Увеличить ширину' }))
    await waitFor(() =>
      expect(
        screen
          .getByRole('img', { name: 'Схема материала' })
          .closest('figure')
          ?.style.getPropertyValue('--vmsh-source-width'),
      ).toBe('12.5rem'),
    )
    await user.keyboard('{Escape}')
    await user.click(screen.getByRole('button', { name: 'Действия с рисунком: Схема материала' }))
    await user.click(screen.getByRole('button', { name: 'В следующую задачу' }))
    await waitFor(() =>
      expect(save).toHaveBeenLastCalledWith(source.revisionId, 1, [
        expect.objectContaining({ targetOrdinal: 2, widthRem: 12.5 }),
      ]),
    )
    const secondTask = screen.getByRole('heading', { name: 'Задача 2.' }).closest('section')!
    await waitFor(() =>
      expect(within(secondTask).getByRole('img', { name: 'Схема материала' })).toBeTruthy(),
    )
    await user.click(
      await screen.findByRole('button', { name: 'Действия с рисунком: Схема материала' }),
    )
    await user.click(screen.getByRole('button', { name: 'Скрыть рисунок' }))
    const hidden = await screen.findByRole('button', { name: 'Восстановить' })
    expect(
      screen.queryByRole('button', { name: 'Действия с рисунком: Схема материала' }),
    ).toBeNull()
    await user.click(hidden)
    await screen.findByRole('button', { name: 'Действия с рисунком: Схема материала' })
    const firstTask = screen.getByRole('heading', { name: 'Задача 1.' }).closest('section')!
    await user.click(
      within(firstTask).getByRole('button', { name: kind === 'hint' ? 'Решение' : 'Подсказка' }),
    )
    expect(within(firstTask).getByRole('img', { name: 'Схема соседнего материала' })).toBeTruthy()
    expect(
      screen.queryByRole('button', { name: 'Размер и размещение: Схема соседнего материала' }),
    ).toBeNull()
    queryClient.clear()
  },
)
