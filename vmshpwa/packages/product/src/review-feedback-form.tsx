import { useEffect, useId, useRef, useState } from 'react'

import { Button, Textarea, cn } from '@vmsh/ui'

import { reactionsForScope } from './reaction'
import { ReactionPicker } from './reaction-picker'
import { VerdictActions } from './review-verdict-actions'
import type { VerdictView } from './types'

const teacherWrittenReactions = reactionsForScope('teacher-written')

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

export interface ReviewFeedbackDraft {
  verdictValue: string | null
  comment: string
  reactionId: number | null
}

export interface ReviewFeedbackFormProps {
  verdicts: VerdictView[]
  onSubmit: (result: ReviewFeedbackResult) => void
  initialDraft?: ReviewFeedbackDraft
  onDraftChange?: (draft: ReviewFeedbackDraft) => void
  disabled?: boolean
  showInternalReaction?: boolean
  className?: string
}

export function ReviewFeedbackForm({
  verdicts,
  onSubmit,
  initialDraft,
  onDraftChange,
  disabled,
  showInternalReaction = true,
  className,
}: ReviewFeedbackFormProps) {
  const commentId = useId()
  const [comment, setComment] = useState(initialDraft?.comment ?? '')
  const [verdict, setVerdict] = useState<VerdictView | null>(
    () => verdicts.find((item) => item.value === initialDraft?.verdictValue) ?? null,
  )
  const [reactionId, setReactionId] = useState<number | null>(initialDraft?.reactionId ?? null)
  const [confirming, setConfirming] = useState(false)
  const formRef = useRef<HTMLFormElement>(null)

  useEffect(() => {
    const send = (event: KeyboardEvent) => {
      if (disabled || event.repeat || event.isComposing) return
      if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
        event.preventDefault()
        formRef.current?.requestSubmit()
      }
    }
    window.addEventListener('keydown', send)
    return () => window.removeEventListener('keydown', send)
  }, [disabled])

  const submit = () => {
    if (disabled || !verdict) return
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
      ref={formRef}
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
            const nextComment = event.target.value
            setComment(nextComment)
            onDraftChange?.({
              verdictValue: verdict?.value ?? null,
              comment: nextComment,
              reactionId,
            })
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
          onDraftChange?.({ verdictValue: picked.value, comment, reactionId })
          setConfirming(false)
        }}
        selectedValue={verdict?.value}
        verdicts={verdicts}
      />

      {showInternalReaction ? (
        <ReactionPicker
          compact
          hotkeys={!disabled}
          legend="Внутренняя пометка (не видна ученику)"
          onSelect={(nextReactionId) => {
            setReactionId(nextReactionId)
            onDraftChange?.({
              verdictValue: verdict?.value ?? null,
              comment,
              reactionId: nextReactionId,
            })
          }}
          options={teacherWrittenReactions}
          value={reactionId}
        />
      ) : null}

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
      <p className="text-caption text-muted-foreground">
        ⌘/Ctrl + Enter — отправить вердикт. Работает и в комментарии.
      </p>
    </form>
  )
}
