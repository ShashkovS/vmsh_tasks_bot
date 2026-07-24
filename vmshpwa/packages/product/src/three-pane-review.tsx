import type { ReactNode } from 'react'

import { cn } from '@vmsh/ui'

/*
 * Three-pane review workspace: queue / immutable evidence / feedback + verdict.
 * On narrow screens the panes stack in the same reading order — the accessible,
 * non-resizable fallback to the desktop resizable layout.
 */
export interface ThreePaneReviewProps {
  queue: ReactNode
  evidence: ReactNode
  feedback: ReactNode
  className?: string
}

export function ThreePaneReview({ queue, evidence, feedback, className }: ThreePaneReviewProps) {
  return (
    <div
      className={cn(
        'grid gap-4 lg:grid-cols-[minmax(0,17rem)_minmax(0,1fr)_minmax(0,22rem)]',
        className,
      )}
    >
      <section aria-label="Очередь" className="min-w-0">
        {queue}
      </section>
      <section aria-label="Работа ученика" className="min-w-0">
        {evidence}
      </section>
      <section aria-label="Проверка" className="min-w-0">
        {feedback}
      </section>
    </div>
  )
}
