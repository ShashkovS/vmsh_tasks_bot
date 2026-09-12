import type { WrittenReviewProjection } from '@vmsh/contracts'
import { useState } from 'react'

import { ReviewAnnotationViewer } from './review-annotation-surface'
import { findReaction, reactionsForScope } from './reaction'
import { ReactionChip, ReactionPicker } from './reaction-picker'
import { VerdictPanel } from './verdict-panel'
import { writtenReviewVerdict } from './verdict-registry'

export interface WrittenReviewHistoryAttachment {
  attachmentId: string
  mediaPath: string
}

export interface WrittenReviewHistoryEntry {
  attachments: WrittenReviewHistoryAttachment[]
}

export interface WrittenReviewHistoryProps {
  entries: WrittenReviewHistoryEntry[]
  reviews: WrittenReviewProjection[]
  onStudentReactionChange?: (
    reviewId: string,
    reactionId: 0 | 1 | 2 | null,
    expectedVersion: number,
  ) => void
  pendingStudentReactionReviewId?: string | null
  studentReactionError?: { reviewId: string; message: string } | null
  /** Deterministic clock injection for Storybook/tests. */
  reactionNow?: string
}

function reviewDate(value: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'long',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

/** Shared read-only result history for Student and Family audiences. */
export function WrittenReviewHistory({
  entries,
  reviews,
  onStudentReactionChange,
  pendingStudentReactionReviewId,
  studentReactionError,
  reactionNow,
}: WrittenReviewHistoryProps) {
  const [mountedAt] = useState(() => Date.now())
  if (reviews.length === 0) return null
  const attachments = new Map(
    entries.flatMap((entry) =>
      entry.attachments.map((attachment) => [attachment.attachmentId, attachment] as const),
    ),
  )

  return (
    <section aria-label="История проверок" className="space-y-4">
      {[...reviews].reverse().map((review, index) => {
        const currentReaction =
          review.studentReaction?.reactionId === null
            ? null
            : findReaction(review.studentReaction?.reactionId ?? -1)
        const editableUntil =
          review.studentReaction?.editableUntil ??
          new Date(new Date(review.completedAt).getTime() + 60 * 60 * 1000).toISOString()
        const editable =
          new Date(reactionNow ?? mountedAt).getTime() <= new Date(editableUntil).getTime()
        const pending = pendingStudentReactionReviewId === review.reviewId
        return (
          <section
            aria-label={index === 0 ? 'Последняя проверка' : 'Прошлая проверка'}
            className="space-y-3"
            key={review.reviewId}
          >
            <VerdictPanel
              at={reviewDate(review.completedAt)}
              author={review.reviewerName}
              comment={review.comment}
              verdict={writtenReviewVerdict(
                review.verdict,
                review.source === 'ai' ? 'ai' : 'human',
              )}
            />
            {onStudentReactionChange && editable ? (
              <ReactionPicker
                disabled={pending}
                legend="Ваша реакция на проверку"
                onSelect={(reactionId) =>
                  onStudentReactionChange(
                    review.reviewId,
                    reactionId as 0 | 1 | 2 | null,
                    review.studentReaction?.version ?? 0,
                  )
                }
                options={reactionsForScope('student-written')}
                value={review.studentReaction?.reactionId ?? null}
              />
            ) : currentReaction ? (
              <div className="space-y-1">
                <p className="text-caption text-muted-foreground">
                  {onStudentReactionChange ? 'Ваша реакция' : 'Реакция ученика'}
                </p>
                <ReactionChip reaction={currentReaction} />
              </div>
            ) : null}
            {studentReactionError?.reviewId === review.reviewId ? (
              <p className="text-small text-danger" role="alert">
                {studentReactionError.message}
              </p>
            ) : null}
            {review.annotations.map((annotation, annotationIndex) => {
              const attachment = attachments.get(annotation.attachmentId)
              if (!attachment) return null
              return (
                <ReviewAnnotationViewer
                  imageAlt={`Проверенная страница решения ${annotationIndex + 1}`}
                  imageSource={attachment.mediaPath}
                  key={`${review.reviewId}:${annotation.attachmentId}`}
                  manifest={annotation}
                />
              )
            })}
          </section>
        )
      })}
    </section>
  )
}
