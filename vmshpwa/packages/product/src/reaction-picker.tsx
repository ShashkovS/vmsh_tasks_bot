import { cn } from '@vmsh/ui'

import { isInternalReactionScope, type ReactionOption } from './reaction'

/*
 * Reaction picker — a single optional reaction. Tapping the selected one clears
 * it. `compact` is the dense teacher fast flow: the exact wording stays visible
 * next to the emoji, but the controls lose the large student touch treatment.
 * When the scope is a teacher-internal one, the picker states plainly that the
 * student never sees it.
 */
export interface ReactionPickerProps {
  options: ReactionOption[]
  value: number | null
  onSelect: (id: number | null) => void
  legend?: string
  compact?: boolean
  disabled?: boolean
  className?: string
}

export function ReactionPicker({
  options,
  value,
  onSelect,
  legend,
  compact,
  disabled,
  className,
}: ReactionPickerProps) {
  const internal = options.length > 0 && isInternalReactionScope(options[0]!.scope)
  return (
    <div className={cn(compact ? 'space-y-1' : 'space-y-2', className)}>
      {legend ? (
        <p className={cn('font-medium text-foreground', compact ? 'text-caption' : 'text-label')}>
          {legend}
        </p>
      ) : null}
      <div
        aria-label={legend ?? 'Реакция'}
        className={cn('flex flex-wrap', compact ? 'gap-1' : 'gap-2')}
        role="group"
      >
        {options.map((option) => {
          const selected = value === option.id
          const tone = selected
            ? 'border-primary bg-primary/10 font-medium text-foreground'
            : 'border-border bg-surface text-muted-foreground hover:bg-surface-subtle hover:text-foreground'
          const onClick = () => onSelect(selected ? null : option.id)
          if (compact) {
            return (
              <button
                aria-pressed={selected}
                className={cn(
                  'inline-flex min-h-7 items-center gap-1 rounded-md border px-2 py-1 text-caption leading-tight transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring',
                  tone,
                )}
                disabled={disabled}
                key={option.id}
                onClick={onClick}
                title={option.label}
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
        <p className="text-caption text-muted-foreground">
          {compact
            ? 'Не видна ученику и семье.'
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
