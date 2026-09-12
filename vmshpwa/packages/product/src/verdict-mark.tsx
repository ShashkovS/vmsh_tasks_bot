import { cn } from '@vmsh/ui'

import type { VerdictView } from './types'

/*
 * Verdict mark. The math symbol is primary; the wording is the accessible name
 * (and visible when `showLabel`). Colour by tone assists but never carries
 * meaning alone. An AI verdict is unmistakably marked (dashed border + robot +
 * «оценка ИИ») and can never be confused with a live teacher.
 */
const surfaceByTone: Record<VerdictView['tone'], string> = {
  none: 'border-verdict-none bg-verdict-none-surface text-verdict-none',
  negative: 'border-verdict-negative bg-verdict-negative-surface text-verdict-negative',
  'partial-low':
    'border-verdict-partial-low bg-verdict-partial-low-surface text-verdict-partial-low',
  'partial-mid':
    'border-verdict-partial-mid bg-verdict-partial-mid-surface text-verdict-partial-mid',
  'partial-high':
    'border-verdict-partial-high bg-verdict-partial-high-surface text-verdict-partial-high',
  positive: 'border-verdict-positive bg-verdict-positive-surface text-verdict-positive',
}

export interface VerdictMarkProps {
  verdict: VerdictView
  showLabel?: boolean
  className?: string
}

export function VerdictMark({ verdict, showLabel = false, className }: VerdictMarkProps) {
  const isAi = verdict.provenance === 'ai'
  const accessibleLabel = `${verdict.label || 'Нет ответа'}${isAi ? ' · оценка ИИ' : ''}`

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md border px-1.5 py-0.5 text-label font-semibold',
        surfaceByTone[verdict.tone],
        isAi && 'border-dashed',
        className,
      )}
      title={accessibleLabel}
    >
      {isAi ? (
        <span aria-hidden="true" className="text-provenance-ai">
          🤖
        </span>
      ) : null}
      <span aria-hidden="true" className="font-num">
        {verdict.symbol || '—'}
      </span>
      <span className={showLabel ? undefined : 'sr-only'}>{accessibleLabel}</span>
    </span>
  )
}
