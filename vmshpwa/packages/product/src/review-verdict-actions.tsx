import { useEffect } from 'react'

import { cn } from '@vmsh/ui'

import type { VerdictView } from './types'
import { VerdictMark } from './verdict-mark'

/*
 * Verdict actions for the review pane. Built from the course registry and
 * ordered best → worst, so digit `1` is always `+`. Buttons and digit keys both
 * work; the digit shortcuts are ignored while focus is in an editable field, and
 * the legend is visible.
 */
export interface VerdictActionsProps {
  verdicts: VerdictView[]
  onPick: (verdict: VerdictView) => void
  selectedValue?: string | undefined
  disabled?: boolean | undefined
  className?: string | undefined
}

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  const tag = target.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || target.isContentEditable
}

export function VerdictActions({
  verdicts,
  onPick,
  selectedValue,
  disabled,
  className,
}: VerdictActionsProps) {
  const ordered = [...verdicts].sort((a, b) => b.weight - a.weight)

  useEffect(() => {
    if (disabled) return
    function onKeyDown(event: KeyboardEvent) {
      if (event.altKey || event.ctrlKey || event.metaKey) return
      if (isEditableTarget(document.activeElement)) return
      const digit = Number(event.key)
      if (!Number.isInteger(digit) || digit < 1 || digit > ordered.length) return
      event.preventDefault()
      onPick(ordered[digit - 1]!)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [ordered, onPick, disabled])

  return (
    <div className={cn('space-y-2', className)}>
      <div className="flex flex-wrap gap-2" role="group">
        {ordered.map((verdict, index) => {
          const selected = verdict.value === selectedValue
          return (
            <button
              aria-pressed={selected}
              className={cn(
                'inline-flex min-h-(--touch-target) items-center gap-2 rounded-md border px-3 text-small transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring',
                selected
                  ? 'border-primary bg-primary/10 font-medium text-foreground'
                  : 'border-border bg-surface text-foreground hover:bg-surface-subtle',
              )}
              disabled={disabled}
              key={verdict.value}
              onClick={() => onPick(verdict)}
              type="button"
            >
              <kbd className="rounded border border-border bg-surface-subtle px-1 font-num text-caption text-muted-foreground">
                {index + 1}
              </kbd>
              <VerdictMark showLabel verdict={verdict} />
            </button>
          )
        })}
      </div>
      <p className="text-caption text-muted-foreground">
        Клавиши 1–{ordered.length}: от лучшего к худшему, 1 — «+». Не срабатывают в поле ввода.
      </p>
    </div>
  )
}
