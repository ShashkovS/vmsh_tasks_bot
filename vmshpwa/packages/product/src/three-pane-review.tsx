import type { ReactNode } from 'react'

import { cn } from '@vmsh/ui'

/*
 * Review workspace: queue plus one chronological work column. The immutable
 * evidence is followed by the existing discussion and only then by the
 * teacher's reply + verdict, so checking reads like one continuous thread.
 */
export interface ThreePaneReviewProps {
  queue: ReactNode
  evidence: ReactNode
  discussion?: ReactNode
  feedback: ReactNode
  className?: string
}

export function ThreePaneReview({
  queue,
  evidence,
  discussion,
  feedback,
  className,
}: ThreePaneReviewProps) {
  return (
    <div className={cn('grid gap-3', className)}>
      <section aria-label="Ветки задачи" className="min-w-0">
        {queue}
      </section>
      <section aria-label="Работа и обсуждение" className="min-w-0 space-y-3">
        <div>{evidence}</div>
        {discussion ? <div>{discussion}</div> : null}
        <div className="rounded-md border border-border bg-surface p-3">{feedback}</div>
      </section>
    </div>
  )
}
