import { History } from 'lucide-react'
import type { ReactNode } from 'react'

import { cn } from '@vmsh/ui'

import { LevelChip } from './level-chip'
import { TaskTypeIcon, taskTypeName } from './task-type'
import type { GroupView, TaskType, VerdictView } from './types'
import { VerdictMark } from './verdict-mark'

/*
 * Problem header — the fixed frame around a task. Type is an icon (with an
 * accessible name + hover title), not a word; the level shows its word; the
 * final verdict, when present, sits here with its wording. `deadline` and the
 * statement body render below, supplied by the page — the condition is never
 * hidden behind this.
 */
export interface ProblemHeaderProps {
  number: string
  title: string
  type: TaskType
  level?: GroupView
  verdict?: VerdictView
  /** A <DeadlineNotice> (or similar), rendered under the meta row. */
  deadline?: ReactNode
  onShowHistory?: () => void
  className?: string
}

export function ProblemHeader({
  number,
  title,
  type,
  level,
  verdict,
  deadline,
  onShowHistory,
  className,
}: ProblemHeaderProps) {
  return (
    <header className={cn('space-y-2', className)}>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5">
        <span className="font-num text-small font-semibold text-muted-foreground">{number}</span>
        <span className="inline-flex" title={taskTypeName(type)}>
          <TaskTypeIcon type={type} />
        </span>
        {level ? <LevelChip level={level} /> : null}
        {verdict ? <VerdictMark showLabel verdict={verdict} /> : null}
        {onShowHistory ? (
          <button
            className="ml-auto inline-flex items-center gap-1 rounded-sm text-small text-link underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
            onClick={onShowHistory}
            type="button"
          >
            <History aria-hidden="true" className="size-4" />
            История
          </button>
        ) : null}
      </div>
      <h1 className="text-balance font-reading text-title font-semibold text-foreground">
        {title}
      </h1>
      {deadline}
    </header>
  )
}
