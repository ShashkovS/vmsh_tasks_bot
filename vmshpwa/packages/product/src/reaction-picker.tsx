import { useEffect } from 'react'

import { cn } from '@vmsh/ui'

import { isInternalReactionScope, type ReactionOption } from './reaction'

/*
 * Reaction picker — a single optional reaction. Tapping the selected one clears
 * it. `compact` is the dense teacher fast flow: the exact wording stays visible
 * next to the emoji, but the controls lose the large student touch treatment.
 * When the scope is a teacher-internal one, the picker states plainly that the
 * student never sees it. The dense review shortcut follows
 * docs/product-ux-decisions-2026-07.md and
 * dev/design-system/04-product-components.md: Mod+Alt+1…N avoids the browser's
 * tab-switching Mod+digit chord while the exact reaction wording remains visible.
 */
export interface ReactionPickerProps {
  options: ReactionOption[]
  value: number | null
  onSelect: (id: number | null) => void
  legend?: string
  compact?: boolean
  hotkeys?: boolean
  disabled?: boolean
  className?: string
}

export function ReactionPicker({
  options,
  value,
  onSelect,
  legend,
  compact,
  hotkeys,
  disabled,
  className,
}: ReactionPickerProps) {
  const internal = options.length > 0 && isInternalReactionScope(options[0]!.scope)

  useEffect(() => {
    if (!compact || !hotkeys || disabled) return

    function onKeyDown(event: KeyboardEvent) {
      const primaryModifier = event.metaKey || event.ctrlKey
      if (!primaryModifier || !event.altKey || event.shiftKey || event.getModifierState('AltGraph'))
        return

      const digit = Number(event.key)
      if (!Number.isInteger(digit) || digit < 1 || digit > options.length) return

      const option = options[digit - 1]!
      event.preventDefault()
      onSelect(value === option.id ? null : option.id)
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [compact, disabled, hotkeys, onSelect, options, value])

  return (
    <div className={cn(compact ? 'space-y-0.5' : 'space-y-2', className)}>
      {legend ? (
        <p
          className={cn(
            'font-medium text-foreground',
            compact ? 'text-caption leading-tight' : 'text-label',
          )}
        >
          {legend}
        </p>
      ) : null}
      <div
        aria-label={legend ?? 'Реакция'}
        className={cn('flex flex-wrap', compact ? 'gap-0.5' : 'gap-2')}
        role="group"
      >
        {options.map((option, index) => {
          const selected = value === option.id
          const tone = selected
            ? 'border-primary bg-primary/10 font-medium text-foreground'
            : 'border-border bg-surface text-muted-foreground hover:bg-surface-subtle hover:text-foreground'
          const onClick = () => onSelect(selected ? null : option.id)
          if (compact) {
            return (
              <button
                aria-keyshortcuts={
                  hotkeys ? `Control+Alt+${index + 1} Meta+Alt+${index + 1}` : undefined
                }
                aria-pressed={selected}
                className={cn(
                  'inline-flex min-h-6 items-center gap-1 rounded-md border px-1.5 py-0.5 text-caption leading-none transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring',
                  tone,
                )}
                disabled={disabled}
                key={option.id}
                onClick={onClick}
                title={hotkeys ? `${option.label} · ⌘/Ctrl+Alt+${index + 1}` : option.label}
                type="button"
              >
                <span aria-hidden="true">{option.emoji}</span>
                <span>{option.label}</span>
              </button>
            )
          }
          return (
            <button
              aria-pressed={selected}
              className={cn(
                'inline-flex min-h-(--touch-target) items-center gap-1.5 rounded-full border px-3 text-small transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring',
                tone,
              )}
              disabled={disabled}
              key={option.id}
              onClick={onClick}
              type="button"
            >
              <span aria-hidden="true">{option.emoji}</span>
              {option.label}
            </button>
          )
        })}
      </div>
      {internal ? (
        <p className="text-caption leading-tight text-muted-foreground">
          {compact
            ? hotkeys
              ? `⌘/Ctrl + Alt + 1–${options.length} · Не видна ученику и семье.`
              : 'Не видна ученику и семье.'
            : 'Видно только преподавателям и администратору — ученик и семья не увидят.'}
        </p>
      ) : null}
    </div>
  )
}

export function ReactionChip({
  reaction,
  className,
}: {
  reaction: ReactionOption
  className?: string
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border border-border bg-surface px-2.5 py-1 text-small text-foreground',
        className,
      )}
    >
      <span aria-hidden="true">{reaction.emoji}</span>
      {reaction.label}
    </span>
  )
}
