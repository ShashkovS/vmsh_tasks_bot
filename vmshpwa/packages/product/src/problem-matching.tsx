import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { CheckCircle2, Link2 } from 'lucide-react'

import { Alert, AlertContent, AlertDescription, AlertTitle, Badge, Button, cn } from '@vmsh/ui'

/**
 * Controlled visual editor for Phase-2 structural task reconciliation.
 * Network, legacy IDs and draft persistence stay in the Staff application;
 * see `dev/development-plan/06-phase-2-content.md`, MATCH-01..03.
 */
export interface ProblemMatchingCandidate {
  id: string
  number: number
  item: string
  title: string
  typeLabel: string
}

export interface ProblemMatchingItem {
  key: string
  displayNumber: string
  sourceTitle: string | null
  suggestedCandidateId: string | null
}

export type ProblemMatchingSelection =
  | { decision: 'auto_position' | 'manual_match'; candidateId: string }
  | { decision: 'insert_new' | 'omit'; candidateId: null }

export interface ProblemMatchingProps {
  id: string
  items: ProblemMatchingItem[]
  candidates: ProblemMatchingCandidate[]
  selections: Readonly<Record<string, ProblemMatchingSelection | undefined>>
  onSelectionChange: (itemKey: string, selection: ProblemMatchingSelection | undefined) => void
  onCommit: () => void
  pending?: boolean
  error?: string
  staleDraft?: boolean
  className?: string
}

function candidateLabel(candidate: ProblemMatchingCandidate): string {
  const position = `${candidate.number}${candidate.item ? candidate.item : ''}`
  return `${position} · ${candidate.title || t`Без названия`} · ${candidate.typeLabel}`
}

function selectionValue(selection: ProblemMatchingSelection | undefined): string {
  if (!selection) return ''
  return selection.candidateId === null
    ? selection.decision
    : `${selection.decision}:${selection.candidateId}`
}

function parseSelection(value: string): ProblemMatchingSelection | undefined {
  if (!value) return undefined
  if (value === 'insert_new' || value === 'omit') {
    return { decision: value, candidateId: null }
  }
  const separator = value.indexOf(':')
  if (separator < 1) return undefined
  const decision = value.slice(0, separator)
  const candidateId = value.slice(separator + 1)
  if ((decision !== 'auto_position' && decision !== 'manual_match') || !candidateId) {
    return undefined
  }
  return { decision, candidateId }
}

export function ProblemMatching({
  id,
  items,
  candidates,
  selections,
  onSelectionChange,
  onCommit,
  pending = false,
  error,
  staleDraft = false,
  className,
}: ProblemMatchingProps) {
  const candidateById = new Map(candidates.map((candidate) => [candidate.id, candidate]))
  const completed = items.filter((item) => selections[item.key] !== undefined).length
  const allCompleted = completed === items.length

  return (
    <section
      aria-labelledby={`${id}-title`}
      className={cn('space-y-3 rounded-md border border-border bg-surface-subtle p-3', className)}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="flex items-center gap-2 text-small font-semibold" id={`${id}-title`}>
            <Link2 aria-hidden="true" className="size-4" />
            <Trans>Сопоставление задач</Trans>
          </h3>
          <p className="mt-0.5 text-caption text-muted-foreground">
            <Trans>
              Для каждой задачи выберите существующую запись, создайте новую или явно пропустите её.
            </Trans>
          </p>
        </div>
        <Badge variant={allCompleted ? 'success' : 'neutral'}>
          <Trans>
            {completed} из {items.length}
          </Trans>
        </Badge>
      </div>

      {staleDraft ? (
        <Alert tone="warning">
          <AlertContent>
            <AlertTitle>
              <Trans>Серверная версия изменилась</Trans>
            </AlertTitle>
            <AlertDescription>
              <Trans>
                Ваш локальный черновик сохранён. Проверьте решения перед повторной отправкой.
              </Trans>
            </AlertDescription>
          </AlertContent>
        </Alert>
      ) : null}

      <ol className="divide-y divide-border rounded-md border border-border bg-surface">
        {items.map((item) => {
          const suggested = item.suggestedCandidateId
            ? candidateById.get(item.suggestedCandidateId)
            : undefined
          return (
            <li
              className="grid min-w-0 gap-2 p-2 sm:grid-cols-[minmax(10rem,0.7fr)_minmax(18rem,1.3fr)] sm:items-center"
              key={item.key}
            >
              <div className="min-w-0">
                <span className="font-num text-caption text-muted-foreground">
                  <Trans>Задача {item.displayNumber}</Trans>
                </span>
                <p
                  className="truncate text-small font-medium"
                  title={item.sourceTitle ?? undefined}
                >
                  {item.sourceTitle ?? t`Название не извлечено`}
                </p>
              </div>
              <select
                aria-label={t`Сопоставление задачи ${item.displayNumber}`}
                className="h-8 min-w-0 rounded-md border border-input bg-surface px-2 text-small text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                disabled={pending}
                onChange={(event) =>
                  onSelectionChange(item.key, parseSelection(event.target.value))
                }
                value={selectionValue(selections[item.key])}
              >
                <option value="">
                  <Trans>Выберите действие…</Trans>
                </option>
                {suggested ? (
                  <option value={`auto_position:${suggested.id}`}>
                    <Trans>По позиции:</Trans> {candidateLabel(suggested)}
                  </option>
                ) : null}
                {candidates
                  .filter((candidate) => candidate.id !== suggested?.id)
                  .map((candidate) => (
                    <option key={candidate.id} value={`manual_match:${candidate.id}`}>
                      <Trans>Существующая:</Trans> {candidateLabel(candidate)}
                    </option>
                  ))}
                <option value="insert_new">
                  <Trans>Создать новую задачу</Trans>
                </option>
                <option value="omit">
                  <Trans>Не публиковать эту задачу</Trans>
                </option>
              </select>
            </li>
          )
        })}
      </ol>

      {error ? (
        <p className="text-small text-status-danger" role="alert">
          {error}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        <Button disabled={!allCompleted || pending} onClick={onCommit} size="sm">
          {pending ? t`Сохраняем…` : t`Подтвердить сопоставление`}
        </Button>
        {allCompleted ? (
          <span className="inline-flex items-center gap-1 text-caption text-status-success">
            <CheckCircle2 aria-hidden="true" className="size-3.5" />{' '}
            <Trans>Все строки заполнены</Trans>
          </span>
        ) : (
          <span className="text-caption text-muted-foreground">
            <Trans>Публикация останется недоступной до заполнения всех строк.</Trans>
          </span>
        )}
      </div>
    </section>
  )
}
