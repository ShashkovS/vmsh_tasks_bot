import { Trans } from '@lingui/react/macro'
import { currentLocale, dateTimeFormat } from '@vmsh/i18n'
import type { ReactNode } from 'react'
import type { AiReviewSuggestion } from '@vmsh/contracts'
import { Button } from '@vmsh/ui'

const symbols = ['−', '−·', '−+', '½', '+−', '+·', '+']

/** Shared optional Staff proposal panel; docs/ai-review-assistant.md. */
export function AiReviewSuggestionsView({
  items,
  currentWork,
  disabled,
  onApply,
  more,
}: {
  items: AiReviewSuggestion[]
  currentWork: boolean
  disabled?: boolean
  onApply: (item: AiReviewSuggestion, field: 'comment' | 'verdict') => void
  more?: ReactNode
}) {
  if (items.length === 0) return null
  return (
    <details open className="space-y-3 rounded-lg border border-border bg-surface p-3">
      <summary className="cursor-pointer text-label font-semibold">
        <Trans>Предложения ИИ</Trans>
      </summary>
      {items.map((item) => {
        const current = Boolean(currentWork && item.isCurrent)
        return (
          <article key={item.suggestionId} className="space-y-2 border-t border-border pt-3">
            <p className="text-caption text-muted-foreground">
              {item.source}
              {item.model ? ` · ${item.model}` : ''} ·{' '}
              <time dateTime={item.createdAt}>
                {dateTimeFormat(currentLocale(), {
                  dateStyle: 'medium',
                  timeStyle: 'short',
                }).format(new Date(item.createdAt))}
              </time>
            </p>
            {!current && (
              <p className="text-small text-muted-foreground">
                <Trans>Предложение устарело или материалы требуют обновления.</Trans>
              </p>
            )}
            {item.comment && <p className="whitespace-pre-wrap text-small">{item.comment}</p>}
            {item.verdict !== null && (
              <p className="text-small">
                <Trans>Предложенный вердикт:</Trans> {symbols[item.verdict - 11]}
              </p>
            )}
            {item.analysis && (
              <details>
                <summary className="cursor-pointer text-small">
                  <Trans>Разбор для преподавателя</Trans>
                </summary>
                <p className="whitespace-pre-wrap text-small">{item.analysis}</p>
              </details>
            )}
            <div className="flex flex-wrap gap-2">
              {item.comment && (
                <Button
                  size="sm"
                  variant="outline"
                  disabled={disabled || !current}
                  onClick={() => onApply(item, 'comment')}
                >
                  <Trans>Добавить комментарий</Trans>
                </Button>
              )}
              {item.verdict !== null && (
                <Button
                  size="sm"
                  variant="outline"
                  disabled={disabled || !current}
                  onClick={() => onApply(item, 'verdict')}
                >
                  <Trans>Выбрать вердикт</Trans>
                </Button>
              )}
            </div>
          </article>
        )
      })}
      {more}
    </details>
  )
}
