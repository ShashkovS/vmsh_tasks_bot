import type { WrittenReviewProjection } from '@vmsh/contracts'

import { ReviewAnnotationViewer } from './review-annotation-surface'
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
export function WrittenReviewHistory({ entries, reviews }: WrittenReviewHistoryProps) {
  if (reviews.length === 0) return null
  const attachments = new Map(
    entries.flatMap((entry) =>
      entry.attachments.map((attachment) => [attachment.attachmentId, attachment] as const),
    ),
  )

  return (
    <section aria-label="История проверок" className="space-y-4">
      {[...reviews].reverse().map((review, index) => (
        <section
          aria-label={index === 0 ? 'Последняя проверка' : 'Прошлая проверка'}
          className="space-y-3"
          key={review.reviewId}
        >
          <VerdictPanel
            at={reviewDate(review.completedAt)}
            author={review.reviewerName}
            comment={review.comment}
            verdict={writtenReviewVerdict(review.verdict, review.source === 'ai' ? 'ai' : 'human')}
          />
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
      ))}
    </section>
  )
}
