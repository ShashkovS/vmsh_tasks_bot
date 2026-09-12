import type { ReviewReactionId, ReviewReactionInboxItem } from '@vmsh/contracts'
import { Badge, Button, cn } from '@vmsh/ui'

import { VerdictMark } from './verdict-mark'
import { writtenReviewVerdict } from './verdict-registry'
import { reactionRegistry } from './reaction'

export type ReviewReactionInboxKind = 'all' | 'student' | 'teacher'

export interface ReviewReactionInboxProps {
  items: ReviewReactionInboxItem[]
  kind: ReviewReactionInboxKind
  onKindChange: (kind: ReviewReactionInboxKind) => void
  reactionId?: ReviewReactionId | null
  onReactionIdChange?: (reactionId: ReviewReactionId | null) => void
  onRecheck?: (item: ReviewReactionInboxItem) => void
  recheckingReviewId?: string | null
  className?: string
}

const kindOptions: Array<{ value: ReviewReactionInboxKind; label: string }> = [
  { value: 'all', label: 'Все' },
  { value: 'student', label: 'От учеников' },
  { value: 'teacher', label: 'От преподавателей' },
]

function formattedMoment(value: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

/** Admin-only current reaction inbox. Reactions are context, never a verdict mutation. */
export function ReviewReactionInbox({
  items,
  kind,
  onKindChange,
  reactionId = null,
  onReactionIdChange,
  onRecheck,
  recheckingReviewId = null,
  className,
}: ReviewReactionInboxProps) {
  const visibleReactions = reactionRegistry
    .filter(
      (reaction) => reaction.scope === 'student-written' || reaction.scope === 'teacher-written',
    )
    .filter((reaction) => {
      if (kind === 'student') return reaction.scope === 'student-written'
      if (kind === 'teacher') return reaction.scope === 'teacher-written'
      return true
    })
  return (
    <section className={cn('space-y-3', className)} data-density="staff">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div aria-label="Источник реакции" className="flex flex-wrap gap-1" role="group">
          {kindOptions.map((option) => (
            <Button
              aria-pressed={kind === option.value}
              key={option.value}
              onClick={() => onKindChange(option.value)}
              size="xs"
              variant={kind === option.value ? 'secondary' : 'ghost'}
            >
              {option.label}
            </Button>
          ))}
        </div>
        <p className="text-caption text-muted-foreground" role="status">
          Показано: {items.length}
        </p>
      </div>

      {onReactionIdChange ? (
        <div aria-label="Формулировка реакции" className="flex flex-wrap gap-1" role="group">
          <Button
            aria-pressed={reactionId === null}
            onClick={() => onReactionIdChange(null)}
            size="xs"
            variant={reactionId === null ? 'outline' : 'ghost'}
          >
            Все формулировки
          </Button>
          {visibleReactions.map((reaction) => (
            <Button
              aria-pressed={reactionId === reaction.id}
              key={reaction.id}
              onClick={() => onReactionIdChange(reaction.id as ReviewReactionId)}
              size="xs"
              variant={reactionId === reaction.id ? 'outline' : 'ghost'}
            >
              <span aria-hidden="true">{reaction.emoji}</span>
              {reaction.label}
            </Button>
          ))}
        </div>
      ) : null}

      {items.length === 0 ? (
        <div className="rounded-md border border-dashed border-border px-3 py-6 text-center">
          <p className="text-small font-medium text-foreground">Активных реакций нет</p>
          <p className="mt-1 text-caption text-muted-foreground">
            Здесь появятся реакции учеников и внутренние пометки преподавателей.
          </p>
        </div>
      ) : (
        <div className="grid gap-2">
          {items.map((item) => (
            <article
              aria-label={`${item.student.displayName}: ${item.reactionLabel}`}
              className="rounded-md border border-border bg-surface px-3 py-2"
              key={item.itemId}
            >
              <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <p className="text-small font-semibold text-foreground">
                      {item.student.displayName}
                    </p>
                    <Badge variant={item.kind === 'student' ? 'info' : 'neutral'}>
                      {item.kind === 'student' ? 'Реакция ученика' : 'Пометка преподавателя'}
                    </Badge>
                  </div>
                  <p className="mt-1 text-small font-medium text-foreground">
                    {item.reactionLabel}
                  </p>
                </div>
                <time
                  className="shrink-0 text-caption text-muted-foreground"
                  dateTime={item.updatedAt}
                >
                  {formattedMoment(item.updatedAt)}
                </time>
              </div>

              <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-caption text-muted-foreground">
                <VerdictMark verdict={writtenReviewVerdict(item.verdict)} />
                <span className="font-num text-foreground">{item.problem.problemNumber}</span>
                <span>{item.problem.problemTitle}</span>
                <span aria-hidden="true">·</span>
                <span>{item.problem.groupName}</span>
                <span aria-hidden="true">·</span>
                <span>проверил {item.reviewer.displayName}</span>
              </div>
              {item.comment ? (
                <p className="mt-1 line-clamp-2 text-caption text-muted-foreground">
                  Комментарий: {item.comment}
                </p>
              ) : null}
              <p className="mt-1 text-caption text-muted-foreground">
                Не меняет результат автоматически.
              </p>
              {item.isLatestReview && onRecheck ? (
                <Button
                  aria-expanded={recheckingReviewId === item.reviewId}
                  className="mt-2"
                  onClick={() => onRecheck(item)}
                  size="xs"
                  variant="outline"
                >
                  Перепроверить результат
                </Button>
              ) : !item.isLatestReview ? (
                <Badge className="mt-2" variant="neutral">
                  Уже есть более новая проверка
                </Badge>
              ) : null}
            </article>
          ))}
        </div>
      )}
    </section>
  )
}
