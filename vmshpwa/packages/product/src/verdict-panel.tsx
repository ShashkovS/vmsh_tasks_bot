import { UserRound } from 'lucide-react'
import type { ReactNode } from 'react'

import { cn } from '@vmsh/ui'

import type { VerdictView } from './types'
import { VerdictMark } from './verdict-mark'

/*
 * The result of a check: the verdict with its wording, who gave it and when,
 * and the comment. A human check and an AI check use visibly different author
 * treatments — even under an AI-verdict policy a student must never mistake AI
 * for a live teacher, and can always escalate to a human.
 */
export interface VerdictPanelProps {
  verdict: VerdictView
  author?: string
  at?: string
  comment?: ReactNode
  className?: string
}

export function VerdictPanel({ verdict, author, at, comment, className }: VerdictPanelProps) {
  const ai = verdict.provenance === 'ai'
  return (
    <section
      aria-label="Результат проверки"
      className={cn(
        'space-y-2 rounded-lg border p-4',
        ai
          ? 'border-dashed border-provenance-ai-border bg-provenance-ai-surface'
          : 'border-border bg-surface',
        className,
      )}
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <VerdictMark showLabel verdict={verdict} />
        {!ai && author ? (
          <span className="inline-flex items-center gap-1.5 text-small text-muted-foreground">
            <UserRound aria-hidden="true" className="size-4 text-provenance-human" />
            {author}
          </span>
        ) : null}
        {at ? <time className="text-caption text-muted-foreground">{at}</time> : null}
      </div>

      {comment ? (
        <div className="font-reading text-body leading-relaxed text-foreground">{comment}</div>
      ) : null}

      {ai ? (
        <p className="text-caption text-muted-foreground">
          Проверил ИИ. Если что-то не так — напишите, и работу посмотрит преподаватель.
        </p>
      ) : null}
    </section>
  )
}
