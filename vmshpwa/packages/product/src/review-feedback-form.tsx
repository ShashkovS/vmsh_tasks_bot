import { useId, useState } from 'react'

import { Button, Textarea, cn } from '@vmsh/ui'

import { reactionsForScope } from './reaction'
import { ReactionPicker } from './reaction-picker'
import { VerdictActions } from './review-verdict-actions'
import type { VerdictView } from './types'

/*
 * Feedback + verdict pane. Embeds the comment guard: a verdict below «+» with an
 * empty comment asks for confirmation (but never blocks); «+» without a comment
 * saves straight away. The staff reaction is internal and never reaches the
 * student.
 */
export interface ReviewFeedbackResult {
  verdict: VerdictView
  comment: string
  reactionId: number | null
}

export interface ReviewFeedbackFormProps {
  verdicts: VerdictView[]
  onSubmit: (result: ReviewFeedbackResult) => void
  disabled?: boolean
  className?: string
}

export function ReviewFeedbackForm({
  verdicts,
  onSubmit,
  disabled,
  className,
}: ReviewFeedbackFormProps) {
  const commentId = useId()
  const [comment, setComment] = useState('')
  const [verdict, setVerdict] = useState<VerdictView | null>(null)
  const [reactionId, setReactionId] = useState<number | null>(null)
  const [confirming, setConfirming] = useState(false)

  const submit = () => {
    if (!verdict) return
    // «Зачтено» — вес ≥ 0.9. Незачёт без комментария просим подтвердить.
    const notPassed = verdict.weight < 0.9
    if (notPassed && comment.trim() === '' && !confirming) {
      setConfirming(true)
      return
    }
    onSubmit({ verdict, comment: comment.trim(), reactionId })
    setConfirming(false)
  }

  return (
    <form
      className={cn('space-y-3', className)}
      onSubmit={(event) => {
        event.preventDefault()
        submit()
      }}
    >
      <div className="space-y-1.5">
        <label className="block text-label font-medium text-foreground" htmlFor={commentId}>
          Комментарий
        </label>
        <Textarea
          className="min-h-16 text-small"
          disabled={disabled}
          id={commentId}
          onChange={(event) => {
            setComment(event.target.value)
            setConfirming(false)
          }}
          placeholder="Что получилось, что стоит поправить…"
          value={comment}
        />
      </div>

      <VerdictActions
        disabled={disabled}
        onPick={(picked) => {
          setVerdict(picked)
          setConfirming(false)
        }}
        selectedValue={verdict?.value}
        verdicts={verdicts}
      />

      <ReactionPicker
        compact
        legend="Внутренняя пометка (не видна ученику)"
        onSelect={setReactionId}
        options={reactionsForScope('teacher-written')}
        value={reactionId}
      />

      {confirming ? (
        <div
          className="space-y-2 rounded-md border border-status-warning-border bg-status-warning-surface p-3 text-small"
          role="group"
        >
          <p className="text-foreground">Незачёт без комментария. Отправить всё равно?</p>
          <div className="flex gap-2">
            <Button onClick={submit} size="sm">
              Отправить всё равно
            </Button>
            <Button onClick={() => setConfirming(false)} size="sm" variant="ghost">
              Добавить комментарий
            </Button>
          </div>
        </div>
      ) : (
        <Button disabled={disabled || !verdict} size="lg" type="submit">
          Отправить вердикт
        </Button>
      )}
    </form>
  )
}
