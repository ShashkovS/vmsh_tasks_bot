import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiResponseError, type FigureLayoutEntry, type WebContentDocument } from '@vmsh/contracts'
import type { ContentApiClient } from '@vmsh/content'
import { Button } from '@vmsh/ui'

/** Revision-scoped drafts, explicit publication; docs/figure-layout.md. */
export function FigureLayoutEditor({
  client,
  revisionId,
  onPreview,
}: {
  client: ContentApiClient
  revisionId: string
  onPreview: (document: WebContentDocument) => void
}) {
  const [opened, setOpened] = useState(false)
  const queryClient = useQueryClient()
  const key = ['staff-figure-layout', revisionId]
  const query = useQuery({
    queryKey: key,
    queryFn: () => client.figureLayout!(revisionId),
    enabled: opened && !!client.figureLayout,
    meta: { realtimeResources: [] },
  })
  const save = useMutation({
    mutationFn: (entries: FigureLayoutEntry[]) =>
      client.saveFigureLayout!(revisionId, query.data!.version, entries),
    onSuccess: (data) => {
      queryClient.setQueryData(key, data)
      onPreview(data.document)
    },
  })
  const error = save.error ?? query.error
  const update = (entry: FigureLayoutEntry) =>
    save.mutate([
      ...(query.data?.entries ?? []).filter((e) => e.occurrenceId !== entry.occurrenceId),
      entry,
    ])
  const reorder = (entry: FigureLayoutEntry, direction: number) => {
    if (!query.data) return
    const siblings = query.data.figures
      .flatMap((row, index) => {
        if (row.figure.type !== 'figure') return []
        const value = query.data.entries.find((e) => e.occurrenceId === row.occurrenceId) ?? {
          occurrenceId: row.occurrenceId,
          targetOrdinal: row.sourceOrdinal,
          targetPart: row.sourcePart,
          section: row.sourceSection,
          order: index,
          side: row.figure.floatHint ?? 'right',
          hidden: false,
        }
        return value.targetOrdinal === entry.targetOrdinal &&
          value.targetPart === entry.targetPart &&
          value.section === entry.section &&
          !value.hidden
          ? [value]
          : []
      })
      .sort((a, b) => a.order - b.order || a.occurrenceId.localeCompare(b.occurrenceId))
    const index = siblings.findIndex((e) => e.occurrenceId === entry.occurrenceId)
    const other = index + direction
    if (index < 0 || other < 0 || other >= siblings.length) return
    ;[siblings[index], siblings[other]] = [siblings[other]!, siblings[index]!]
    const ids = new Set(siblings.map((e) => e.occurrenceId))
    save.mutate([
      ...query.data.entries.filter((e) => !ids.has(e.occurrenceId)),
      ...siblings.map((e, order) => ({ ...e, order })),
    ])
  }
  return (
    <details
      className="mt-4 rounded border border-border p-3"
      onToggle={(e) => setOpened(e.currentTarget.open)}
    >
      <summary className="cursor-pointer font-medium">Расположение рисунков</summary>
      <p className="my-2 text-small text-muted-foreground">
        Правки появятся у школьников после публикации.
      </p>
      {query.isLoading ? <p role="status">Загружаем рисунки…</p> : null}
      {query.isError || save.isError ? (
        <div role="alert">
          <p>
            {error instanceof ApiResponseError && error.code === 'recompile_required'
              ? 'Для этой версии сначала нажмите «Повторно обработать исходник» над предпросмотром.'
              : error instanceof ApiResponseError && error.status === 409
                ? 'Расположение уже изменилось. Обновите данные и повторите действие.'
                : 'Не удалось сохранить или загрузить расположение. Обновите данные и повторите действие.'}
          </p>
          <Button
            onClick={() => {
              save.reset()
              void query.refetch()
            }}
          >
            Обновить
          </Button>
        </div>
      ) : null}
      {query.data ? (
        <div className="space-y-3">
          {[false, true].map((hidden) => (
            <section key={String(hidden)} aria-label={hidden ? 'Скрытые рисунки' : 'Рисунки'}>
              {hidden ? <h3 className="font-medium">Скрытые рисунки</h3> : null}
              {query.data.figures.map((row, index) => {
                const original =
                  query.data.document.problems.find((p) => p.ordinal === row.sourceOrdinal) ??
                  query.data.document.problems[0]
                if (!original || row.figure.type !== 'figure') return null
                const entry = query.data.entries.find(
                  (e) => e.occurrenceId === row.occurrenceId,
                ) ?? {
                  occurrenceId: row.occurrenceId,
                  targetOrdinal: original.ordinal,
                  targetPart: row.sourcePart,
                  section: row.sourceSection,
                  order: index,
                  side: row.figure.floatHint ?? ('right' as const),
                  hidden: false,
                }
                if (entry.hidden !== hidden) return null
                const target = query.data.document.problems.find(
                  (p) => p.ordinal === entry.targetOrdinal,
                )!
                return (
                  <fieldset
                    disabled={save.isPending}
                    key={row.occurrenceId}
                    className="my-3 flex min-w-0 flex-wrap items-center gap-2 rounded border border-border p-2"
                  >
                    <legend className="text-small">Рисунок {index + 1}</legend>
                    {row.figure.asset.status === 'available' ? (
                      <img
                        className="h-20 w-24 object-contain"
                        src={row.figure.asset.src}
                        alt={row.figure.alt || `Рисунок ${index + 1}`}
                      />
                    ) : (
                      <span>Рисунок недоступен</span>
                    )}
                    <label className="text-small">
                      Задача
                      <select
                        aria-label="Задача"
                        className="mx-2 max-w-full rounded border border-border bg-surface p-2"
                        value={entry.targetOrdinal}
                        onChange={(e) =>
                          update({
                            ...entry,
                            targetOrdinal: Number(e.target.value),
                            targetPart: null,
                          })
                        }
                      >
                        {query.data.document.problems.map((p) => (
                          <option key={p.ordinal} value={p.ordinal}>
                            {p.taskReference ?? p.sourceItem ?? p.ordinal}
                            {p.title ? ` · ${p.title}` : ''}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="text-small">
                      Пункт
                      <select
                        aria-label="Пункт"
                        className="mx-2 rounded border border-border bg-surface p-2"
                        value={entry.targetPart ?? ''}
                        onChange={(e) => update({ ...entry, targetPart: e.target.value || null })}
                      >
                        <option value="">Общий блок</option>
                        {target.partLabels?.map((label) => (
                          <option key={label}>{label}</option>
                        ))}
                      </select>
                    </label>
                    {query.data.document.materialKind === 'solution' ? (
                      <label className="text-small">
                        Раздел
                        <select
                          aria-label="Раздел"
                          className="mx-2 rounded border border-border bg-surface p-2"
                          value={entry.section}
                          onChange={(e) =>
                            update({
                              ...entry,
                              section: e.target.value as FigureLayoutEntry['section'],
                            })
                          }
                        >
                          <option value="common">Перед ответом и решением</option>
                          <option value="answer">Ответ</option>
                          <option value="solution">Решение</option>
                        </select>
                      </label>
                    ) : null}
                    <label className="text-small">
                      Сторона
                      <select
                        aria-label="Сторона"
                        className="mx-2 rounded border border-border bg-surface p-2"
                        value={entry.side}
                        onChange={(e) =>
                          update({ ...entry, side: e.target.value as 'left' | 'right' })
                        }
                      >
                        <option value="left">Слева</option>
                        <option value="right">Справа</option>
                      </select>
                    </label>
                    <Button size="sm" variant="outline" onClick={() => reorder(entry, -1)}>
                      Выше
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => reorder(entry, 1)}>
                      Ниже
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        const atSource =
                          entry.targetOrdinal === original.ordinal &&
                          entry.targetPart === row.sourcePart &&
                          entry.section === row.sourceSection &&
                          entry.order === index &&
                          entry.side ===
                            (row.figure.type === 'figure'
                              ? (row.figure.floatHint ?? 'right')
                              : 'right')
                        if (hidden && atSource) {
                          save.mutate(
                            query.data.entries.filter((e) => e.occurrenceId !== row.occurrenceId),
                          )
                        } else {
                          update({ ...entry, hidden: !entry.hidden })
                        }
                      }}
                    >
                      {hidden ? 'Восстановить' : 'Скрыть'}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() =>
                        save.mutate(
                          query.data.entries.filter((e) => e.occurrenceId !== row.occurrenceId),
                        )
                      }
                    >
                      Вернуть исходное расположение
                    </Button>
                  </fieldset>
                )
              })}
            </section>
          ))}
        </div>
      ) : null}
    </details>
  )
}
