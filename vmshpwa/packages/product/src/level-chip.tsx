import { cn } from '@vmsh/ui'

import type { LevelView } from './types'

/*
 * Level indicator. The student always sees the WORD («Начинающие»); the letter
 * is a compact marker beside it. `compact` shows the letter alone (dense Staff
 * queue) with the full name as the accessible name — never a bare code to a
 * student. Level colour is categorical, never a grade.
 */
const markerByIndex: Record<LevelView['colorIndex'], string> = {
  0: 'border-level-0-border text-level-0',
  1: 'border-level-1-border text-level-1',
  2: 'border-level-2-border text-level-2',
  3: 'border-level-3-border text-level-3',
  4: 'border-level-4-border text-level-4',
}

export interface LevelChipProps {
  level: LevelView
  compact?: boolean
  className?: string
}

export function LevelChip({ level, compact = false, className }: LevelChipProps) {
  const marker = (
    <span
      aria-hidden="true"
      className={cn(
        'grid size-4 shrink-0 place-items-center rounded-sm border text-caption font-semibold',
        markerByIndex[level.colorIndex],
      )}
    >
      {level.code}
    </span>
  )

  if (compact) {
    return (
      <span
        aria-label={level.name}
        className={cn('inline-flex', className)}
        role="img"
        title={level.name}
      >
        {marker}
      </span>
    )
  }

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md border border-border bg-surface px-2 py-0.5 text-label font-medium text-foreground',
        className,
      )}
    >
      {marker}
      {level.name}
    </span>
  )
}
