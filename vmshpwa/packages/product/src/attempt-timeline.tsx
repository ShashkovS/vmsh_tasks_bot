import { ChevronDown } from 'lucide-react'
import { useState } from 'react'

import { cn } from '@vmsh/ui'

import type { VerdictView } from './types'
import { VerdictMark } from './verdict-mark'

/*
 * History of a task: the latest verdict is shown at once, the rest expands. No
 * mandatory «attempt number» and no accusatory language — a resend of details
 * or replacing one's own solution are ordinary events, not failed attempts.
 */
export interface TimelineEntry {
  id: string
  at: string
  label: string
  verdict?: VerdictView
  detail?: string
}

export interface AttemptTimelineProps {
  /** Newest first. */
  entries: TimelineEntry[]
  className?: string
}

function TimelineRow({ entry, emphasized }: { entry: TimelineEntry; emphasized?: boolean }) {
  return (
    <div className="space-y-1">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span
          className={cn(
            'text-small',
            emphasized ? 'font-medium text-foreground' : 'text-muted-foreground',
          )}
        >
          {entry.label}
        </span>
        {entry.verdict ? <VerdictMark showLabel verdict={entry.verdict} /> : null}
        <time className="font-num text-caption text-muted-foreground">{entry.at}</time>
      </div>
      {entry.detail ? <p className="text-caption text-muted-foreground">{entry.detail}</p> : null}
    </div>
  )
}

export function AttemptTimeline({ entries, className }: AttemptTimelineProps) {
  const [open, setOpen] = useState(false)
  if (entries.length === 0) return null
  const [latest, ...rest] = entries

  return (
    <div className={cn('space-y-2', className)}>
      <TimelineRow emphasized entry={latest!} />
      {rest.length > 0 ? (
        <div className="space-y-2">
          <button
            aria-expanded={open}
            className="inline-flex items-center gap-1 text-small text-link hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
            onClick={() => setOpen((value) => !value)}
            type="button"
          >
            <ChevronDown
              aria-hidden="true"
              className={cn('size-4 transition-transform', open && 'rotate-180')}
            />
            {open ? 'Скрыть историю' : `Показать историю (${rest.length})`}
          </button>
          {open ? (
            <ol className="space-y-3 border-l border-border pl-4">
              {rest.map((entry) => (
                <li key={entry.id}>
                  <TimelineRow entry={entry} />
                </li>
              ))}
            </ol>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
