import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowDown, ArrowUp, MoreHorizontal, Minus, Plus, SlidersHorizontal } from 'lucide-react'
import {
  ApiResponseError,
  type FigureLayout,
  type FigureLayoutEntry,
  type WebContentBlock,
  type WebContentDocument,
} from '@vmsh/contracts'
import type { ContentApiClient, FigureToolsRenderer } from '@vmsh/content'
import { Button, Input, Popover, PopoverContent, PopoverTitle, PopoverTrigger } from '@vmsh/ui'

type Figure = Extract<WebContentBlock, { type: 'figure' }>
type Row = FigureLayout['figures'][number]
type Change = { id: string; patch: Partial<FigureLayoutEntry> | null }
export interface FigureDraftState {
  version: number
  dirty: boolean
  saving: boolean
  canPublish: boolean
}

/** Occurrence identity, source-preserving sizing; docs/figure-layout.md. */
function entryFor(data: FigureLayout, row: Row, index: number): FigureLayoutEntry {
  return (
    data.entries.find((e) => e.occurrenceId === row.occurrenceId) ?? {
      occurrenceId: row.occurrenceId,
      targetOrdinal: row.sourceOrdinal,
      targetPart: row.sourcePart,
      section: row.sourceSection,
      order: index,
      side: row.figure.type === 'figure' ? (row.figure.floatHint ?? 'right') : 'right',
      placement: 'source',
      hidden: false,
    }
  )
}

function previewWidth(
  document: WebContentDocument,
  id: string,
  widthRem: number,
): WebContentDocument {
  const visit = (blocks: WebContentBlock[]): WebContentBlock[] =>
    blocks.map((block) => {
      if (block.type === 'figure' && block.occurrenceId === id) return { ...block, widthRem }
      if (block.type === 'subpart' || block.type === 'callout')
        return { ...block, blocks: visit(block.blocks) }
      if (block.type === 'list') return { ...block, items: block.items.map(visit) }
      return block
    })
  return {
    ...document,
    introduction: visit(document.introduction),
    problems: document.problems.map((p) => ({
      ...p,
      blocks: visit(p.blocks),
      ...(p.preambleBlocks ? { preambleBlocks: visit(p.preambleBlocks) } : {}),
      ...(p.trailingBlocks ? { trailingBlocks: visit(p.trailingBlocks) } : {}),
    })),
  }
}

function FigureControls({
  figure,
  data,
  row,
  entry,
  disabled,
  update,
  reset,
  widthPreview,
  onStaging,
  reorder,
}: {
  figure: Figure
  data: FigureLayout
  row: Row
  entry: FigureLayoutEntry
  disabled: boolean
  update: (patch: Partial<FigureLayoutEntry>) => void
  reset: () => void
  onStaging: (pending: boolean) => void
  widthPreview: (width: number) => void
  reorder: (direction: number) => void
}) {
  const root = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(figure.widthRem ?? 12)
  const [widthText, setWidthText] = useState(String(width))
  const staged = useRef<number | null>(null)
  const index = data.document.problems.findIndex((p) => p.ordinal === entry.targetOrdinal)
  const target = data.document.problems[index]
  const changeWidth = (value: number) => {
    const next = Math.max(0.5, Math.min(80, Math.round(value * 2) / 2))
    setWidth(next)
    setWidthText(String(next))
    staged.current = next
    onStaging(true)
    widthPreview(next)
  }
  const commitWidth = () => {
    if (staged.current === null) return
    const next = staged.current
    staged.current = null
    onStaging(false)
    update({ widthRem: next })
  }
  const move = (ordinal: number) =>
    update({ targetOrdinal: ordinal, targetPart: null, placement: 'center-after' })
  const placement = entry.placement ?? `float-${entry.side}`
  const selectClass = 'w-full rounded border border-border bg-surface p-2 text-small'
  return (
    <div
      ref={root}
      className="flex items-center justify-between gap-2"
      data-figure-controls={row.occurrenceId}
    >
      <Popover
        onOpenChange={(open) => {
          if (open) {
            const rem = Number.parseFloat(getComputedStyle(document.documentElement).fontSize) || 16
            const measured = root.current
              ?.closest('figure')
              ?.querySelector('.vmsh-figure-canvas')
              ?.getBoundingClientRect().width
            const value =
              figure.widthRem ??
              Math.max(0.5, Math.min(80, Math.round(((measured ?? 192) / rem) * 2) / 2))
            setWidth(value)
            setWidthText(String(value))
          } else commitWidth()
        }}
      >
        <PopoverTrigger
          render={
            <Button
              size="icon"
              variant="outline"
              className="bg-surface shadow-sm"
              aria-label={t`Размер и размещение: ${figure.alt}`}
            />
          }
          disabled={disabled}
        >
          <SlidersHorizontal aria-hidden="true" />
        </PopoverTrigger>
        <PopoverContent
          align="start"
          className="max-h-[80dvh] w-72 max-w-[calc(100vw-1rem)] overflow-y-auto font-sans"
          aria-label={t`Размер и размещение`}
        >
          <PopoverTitle>
            <Trans>Размер и размещение</Trans>
          </PopoverTitle>
          <fieldset disabled={disabled} className="space-y-3">
            <legend className="sr-only">
              <Trans>Оформление рисунка</Trans>
            </legend>
            <div className="block text-small">
              <span>
                <Trans>Ширина, rem</Trans>
              </span>
              <div className="mt-1 flex items-center gap-2">
                <Button
                  size="icon"
                  variant="outline"
                  aria-label={t`Уменьшить ширину`}
                  disabled={width <= 0.5}
                  onClick={() => {
                    changeWidth(width - 0.5)
                    commitWidth()
                  }}
                >
                  <Minus aria-hidden="true" />
                </Button>
                <Input
                  type="number"
                  min={0.5}
                  max={80}
                  step={0.5}
                  value={widthText}
                  aria-label={t`Ширина, rem`}
                  onChange={(e) => {
                    setWidthText(e.target.value)
                    const value = e.target.valueAsNumber
                    if (Number.isFinite(value) && value >= 0.5 && value <= 80) {
                      setWidth(value)
                      staged.current = value
                      onStaging(true)
                      widthPreview(value)
                    }
                  }}
                  onBlur={() => {
                    if (staged.current === null) {
                      setWidthText(String(width))
                      return
                    }
                    const value = Number(widthText)
                    if (widthText.trim() && Number.isFinite(value) && value >= 0.5 && value <= 80)
                      changeWidth(value)
                    else setWidthText(String(width))
                    commitWidth()
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && staged.current !== null) {
                      changeWidth(width)
                      commitWidth()
                    }
                  }}
                />
                <Button
                  size="icon"
                  variant="outline"
                  aria-label={t`Увеличить ширину`}
                  disabled={width >= 80}
                  onClick={() => {
                    changeWidth(width + 0.5)
                    commitWidth()
                  }}
                >
                  <Plus aria-hidden="true" />
                </Button>
              </div>
            </div>
            <input
              type="range"
              min={0.5}
              max={40}
              step={0.5}
              value={Math.min(40, width)}
              className="w-full accent-primary"
              aria-label={t`Ширина рисунка`}
              onChange={(e) => changeWidth(Number(e.target.value))}
              onPointerUp={commitWidth}
              onKeyUp={commitWidth}
              onBlur={commitWidth}
            />
            <p className="text-caption text-muted-foreground">
              <Trans>На узком экране рисунок уменьшится до доступной ширины.</Trans>
            </p>
            <label className="block text-small">
              <Trans>Размещение</Trans>
              <select
                className={selectClass}
                aria-label={t`Размещение`}
                value={placement}
                onChange={(e) =>
                  update({ placement: e.target.value as FigureLayoutEntry['placement'] })
                }
              >
                <option value="source">
                  <Trans>По исходнику</Trans>
                </option>
                <option value="center-source">
                  <Trans>В тексте без обтекания</Trans>
                </option>
                <option value="center-before">
                  <Trans>По центру перед текстом</Trans>
                </option>
                <option value="center-after">
                  <Trans>По центру после текста</Trans>
                </option>
                <option value="float-right">
                  <Trans>Обтекание справа</Trans>
                </option>
                <option value="float-left">
                  <Trans>Обтекание слева</Trans>
                </option>
              </select>
            </label>
            <Button size="sm" variant="ghost" onClick={reset}>
              <Trans>Вернуть исходное оформление</Trans>
            </Button>
          </fieldset>
        </PopoverContent>
      </Popover>
      <Popover>
        <PopoverTrigger
          render={
            <Button
              size="icon"
              variant="outline"
              className="bg-surface shadow-sm"
              aria-label={t`Действия с рисунком: ${figure.alt}`}
            />
          }
          disabled={disabled}
          data-figure-actions={row.occurrenceId}
        >
          <MoreHorizontal aria-hidden="true" />
        </PopoverTrigger>
        <PopoverContent
          align="end"
          className="max-h-[80dvh] max-w-[calc(100vw-1rem)] overflow-y-auto font-sans"
          aria-label={t`Действия с рисунком`}
        >
          <PopoverTitle>
            <Trans>Действия с рисунком</Trans>
          </PopoverTitle>
          <fieldset disabled={disabled} className="space-y-2">
            <legend className="sr-only">
              <Trans>Перенос и скрытие</Trans>
            </legend>
            <Button
              className="w-full justify-start"
              size="sm"
              variant="ghost"
              disabled={index <= 0}
              onClick={() => move(data.document.problems[index - 1]!.ordinal)}
            >
              <ArrowUp aria-hidden="true" />
              <Trans>В предыдущую задачу</Trans>
            </Button>
            <Button
              className="w-full justify-start"
              size="sm"
              variant="ghost"
              disabled={index < 0 || index >= data.document.problems.length - 1}
              onClick={() => move(data.document.problems[index + 1]!.ordinal)}
            >
              <ArrowDown aria-hidden="true" />
              <Trans>В следующую задачу</Trans>
            </Button>
            <Button
              className="w-full justify-start"
              size="sm"
              variant="ghost"
              onClick={() => update({ hidden: true })}
            >
              <Trans>Скрыть рисунок</Trans>
            </Button>
            <details className="border-t border-border pt-2">
              <summary className="cursor-pointer text-small">
                <Trans>Дополнительные настройки</Trans>
              </summary>
              <div className="mt-2 space-y-2">
                <label className="block text-small">
                  <Trans>Задача</Trans>
                  <select
                    className={selectClass}
                    aria-label={t`Задача`}
                    value={entry.targetOrdinal}
                    onChange={(e) => move(Number(e.target.value))}
                  >
                    {entry.targetOrdinal === 0 ? (
                      <option value={0}>
                        <Trans>Вступление</Trans>
                      </option>
                    ) : null}
                    {data.document.problems.map((p) => (
                      <option key={p.ordinal} value={p.ordinal}>
                        {p.taskReference ?? p.sourceItem ?? p.ordinal}
                        {p.title ? ` · ${p.title}` : ''}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block text-small">
                  <Trans>Пункт</Trans>
                  <select
                    className={selectClass}
                    aria-label={t`Пункт`}
                    value={entry.targetPart ?? ''}
                    onChange={(e) =>
                      update({
                        targetPart: e.target.value || null,
                        placement:
                          placement === 'source' || placement === 'center-source'
                            ? 'center-before'
                            : entry.placement,
                      })
                    }
                    disabled={!target}
                  >
                    <option value="">
                      <Trans>Общий блок</Trans>
                    </option>
                    {target?.partLabels?.map((label) => (
                      <option key={label}>{label}</option>
                    ))}
                  </select>
                </label>
                {data.document.materialKind === 'solution' ? (
                  <label className="block text-small">
                    <Trans>Раздел</Trans>
                    <select
                      className={selectClass}
                      aria-label={t`Раздел`}
                      value={entry.section}
                      onChange={(e) =>
                        update({
                          section: e.target.value as FigureLayoutEntry['section'],
                          placement:
                            placement === 'source' || placement === 'center-source'
                              ? 'center-before'
                              : entry.placement,
                        })
                      }
                    >
                      <option value="common">
                        <Trans>Общий блок</Trans>
                      </option>
                      <option value="answer">
                        <Trans>Ответ</Trans>
                      </option>
                      <option value="solution">
                        <Trans>Решение</Trans>
                      </option>
                    </select>
                  </label>
                ) : null}
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={() => reorder(-1)}>
                    <Trans>Выше</Trans>
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => reorder(1)}>
                    <Trans>Ниже</Trans>
                  </Button>
                </div>
              </div>
            </details>
          </fieldset>
        </PopoverContent>
      </Popover>
    </div>
  )
}

/** Inline controls share one versioned draft; publication stays explicit. */
export function FigureLayoutEditor({
  client,
  revisionId,
  onPreview,
  onState,
  onSaved,
  children,
}: {
  client: ContentApiClient
  revisionId: string
  onPreview: (document: WebContentDocument) => void
  onState?: (state: FigureDraftState) => void
  onSaved?: () => void
  children?: (renderTools: FigureToolsRenderer) => ReactNode
}) {
  const queryClient = useQueryClient()
  const key = ['staff-figure-layout', revisionId]
  const [staging, setStaging] = useState(false)
  const query = useQuery({
    queryKey: key,
    queryFn: () => client.figureLayout!(revisionId),
    meta: { realtimeResources: [] },
  })
  const save = useMutation({
    scope: { id: `figure-layout:${revisionId}` },
    mutationFn: (changes: Change[]) => {
      const data = queryClient.getQueryData<FigureLayout>(key)!
      let entries = data.entries
      for (const change of changes) {
        const index = data.figures.findIndex((r) => r.occurrenceId === change.id)
        const row = data.figures[index]!
        const entry = entryFor(data, row, index)
        entries = entries.filter((e) => e.occurrenceId !== change.id)
        if (change.patch) entries = [...entries, { ...entry, ...change.patch }]
      }
      return client.saveFigureLayout!(revisionId, data.version, entries)
    },
    onSuccess: (data, changes) => {
      queryClient.setQueryData(key, data)
      onSaved?.()
      const changed = changes[0]
      if (changed?.patch?.hidden || changed?.patch?.targetOrdinal !== undefined)
        requestAnimationFrame(() => {
          const selector = changed.patch?.hidden
            ? `[data-figure-restore="${changed.id}"]`
            : `[data-figure-actions="${changed.id}"]`
          document.querySelector<HTMLButtonElement>(selector)?.focus()
        })
    },
  })
  useEffect(() => {
    if (query.data) onPreview(query.data.document)
  }, [query.data, onPreview])
  useEffect(() => {
    if (query.data)
      onState?.({
        version: query.data.version,
        dirty: query.data.hasUnpublishedChanges ?? query.data.entries.length > 0,
        saving: staging || save.isPending || save.isError,
        canPublish: query.data.canPublish ?? false,
      })
  }, [query.data, staging, save.isPending, save.isError, onState])
  const error = save.error ?? query.error
  const update = (id: string, patch: Partial<FigureLayoutEntry> | null) =>
    save.mutate([{ id, patch }])
  const tools: FigureToolsRenderer = (figure) => {
    const index = query.data?.figures.findIndex((r) => r.occurrenceId === figure.occurrenceId) ?? -1
    if (!query.data || index < 0) return null
    const data = query.data
    const row = data.figures[index]!
    const entry = entryFor(data, row, index)
    return (
      <FigureControls
        key={row.occurrenceId}
        figure={figure}
        data={data}
        row={row}
        entry={entry}
        disabled={save.isPending || save.isError}
        update={(patch) =>
          update(
            row.occurrenceId,
            patch.placement === 'source' || patch.placement === 'center-source'
              ? {
                  ...patch,
                  targetOrdinal: row.sourceOrdinal,
                  targetPart: row.sourcePart,
                  section: row.sourceSection,
                }
              : patch,
          )
        }
        reset={() => update(row.occurrenceId, null)}
        onStaging={setStaging}
        widthPreview={(width) => onPreview(previewWidth(data.document, row.occurrenceId, width))}
        reorder={(direction) => {
          const siblings = data.figures
            .map((r, i) => entryFor(data, r, i))
            .filter(
              (e) =>
                !e.hidden &&
                e.targetOrdinal === entry.targetOrdinal &&
                e.targetPart === entry.targetPart &&
                e.section === entry.section,
            )
            .sort((a, b) => a.order - b.order || a.occurrenceId.localeCompare(b.occurrenceId))
          const at = siblings.findIndex((e) => e.occurrenceId === entry.occurrenceId)
          if (at + direction < 0 || at + direction >= siblings.length) return
          ;[siblings[at], siblings[at + direction]] = [siblings[at + direction]!, siblings[at]!]
          save.mutate(
            siblings.map((e, order) => ({
              id: e.occurrenceId,
              patch: {
                ...e,
                order,
                placement:
                  e.placement === 'source' || e.placement === 'center-source'
                    ? 'center-before'
                    : e.placement,
              },
            })),
          )
        }}
      />
    )
  }
  const loaded = query.data
  const hidden = loaded?.figures.filter((row, i) => entryFor(loaded, row, i).hidden) ?? []
  return (
    <div className="space-y-3">
      {query.isLoading ? (
        <p role="status">
          <Trans>Загружаем настройки рисунков…</Trans>
        </p>
      ) : null}
      {error ? (
        <div role="alert" className="rounded border border-border p-3 text-small">
          <p>
            {error instanceof ApiResponseError && error.code === 'recompile_required'
              ? t`Для этой версии сначала нажмите «Повторно обработать исходник» над предпросмотром.`
              : error instanceof ApiResponseError && error.status === 409
                ? t`Оформление уже изменилось. Обновите данные и повторите действие.`
                : t`Не удалось сохранить или загрузить оформление рисунков.`}
          </p>
          <Button
            size="sm"
            onClick={() => {
              save.reset()
              void query.refetch()
            }}
          >
            <Trans>Обновить</Trans>
          </Button>
        </div>
      ) : null}
      {children?.(tools)}
      {hidden.length ? (
        <details open className="rounded border border-border p-3">
          <summary className="cursor-pointer text-small">
            <Trans>Скрытые рисунки</Trans> ({hidden.length})
          </summary>
          <ul className="mt-2 space-y-2">
            {hidden.map((row) => (
              <li key={row.occurrenceId} className="flex items-center gap-3 text-small">
                {row.figure.type === 'figure' && row.figure.asset.status === 'available' ? (
                  <img
                    className="h-12 w-16 object-contain"
                    src={row.figure.asset.src}
                    alt={row.figure.alt}
                  />
                ) : null}
                <span className="min-w-0 flex-1">
                  {row.figure.type === 'figure' ? row.figure.alt : row.occurrenceId}
                </span>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={save.isPending || save.isError}
                  data-figure-restore={row.occurrenceId}
                  onClick={() => update(row.occurrenceId, { hidden: false })}
                >
                  <Trans>Восстановить</Trans>
                </Button>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  )
}
