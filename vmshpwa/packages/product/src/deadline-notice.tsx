import { cn } from '@vmsh/ui'

/*
 * Deadline: absolute time (Europe/Moscow, publication of solutions) plus a
 * relative phrase. Strings are pre-formatted by the app's date layer — the
 * component stays presentation-only. `closesAt` feeds a machine-readable
 * <time>.
 */
export interface DeadlineNoticeProps {
  closesAt: string
  absoluteLabel: string
  relativeLabel: string
  state?: 'open' | 'closing-soon' | 'closed'
  className?: string
}

const toneByState = {
  open: 'text-foreground',
  'closing-soon': 'text-status-warning',
  closed: 'text-muted-foreground',
} as const

export function DeadlineNotice({
  closesAt,
  absoluteLabel,
  relativeLabel,
  state = 'open',
  className,
}: DeadlineNoticeProps) {
  return (
    <p className={cn('flex flex-wrap items-baseline gap-x-1.5 gap-y-0.5 text-small', className)}>
      <span className={cn('font-medium', toneByState[state])}>
        {state === 'closed' ? 'Приём закрыт' : `Приём до ${absoluteLabel}`}
      </span>
      <time className="text-muted-foreground" dateTime={closesAt}>
        · {relativeLabel}
      </time>
    </p>
  )
}
