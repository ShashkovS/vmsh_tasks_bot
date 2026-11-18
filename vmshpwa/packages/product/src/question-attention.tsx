import { t } from '@lingui/core/macro'
import type { SupportAttentionState } from '@vmsh/contracts'
import { cn } from '@vmsh/ui'

/** docs/question-attention.md; used by StudentProblemQuestionLink. */
export function QuestionAttentionDot({ state }: { state?: SupportAttentionState | undefined }) {
  if (!state || state === 'none') return null
  const label =
    state === 'unread_reply' ? t`Есть непрочитанный ответ` : t`Ждём ответа преподавателя`
  return (
    <span className="inline-flex" title={label}>
      <span
        aria-hidden="true"
        className={cn(
          'size-2 rounded-full',
          state === 'unread_reply'
            ? 'bg-status-danger motion-safe:animate-pulse'
            : 'bg-status-warning',
        )}
      />
      <span className="sr-only">{label}</span>
    </span>
  )
}
