import { cn } from '@vmsh/ui'

import type { LevelView } from './types'

/*
 * Level indicator. The student always sees the WORD («Начинающие»); the letter
 * is a compact marker beside it. Codes may contain one to three characters
 * (`н`, `dp2`, `i9a`); the marker grows horizontally and never clips or shifts
 * its baseline. `compact` shows the code alone in dense Staff views.
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
        'inline-flex h-4 min-w-4 shrink-0 items-center justify-center rounded-sm border px-0.5 font-num text-[10px] font-semibold leading-none',
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
        className={cn('inline-flex items-center', className)}
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
