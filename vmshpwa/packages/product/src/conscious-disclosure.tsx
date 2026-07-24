import { ChevronDown, KeyRound, Lightbulb, Lock, type LucideIcon } from 'lucide-react'
import { useId, useState, type ReactNode } from 'react'

import { Button, cn } from '@vmsh/ui'

/*
 * Hint / solution disclosure. The condition is never inside this — it stays
 * visible above; this is additive. Revealing asks for a conscious confirmation
 * the first time (you cannot «unsee» a solution); once revealed it toggles
 * freely. When not yet available it renders locked, never as a dead control.
 */
export interface ConsciousDisclosureProps {
  label: string
  icon: LucideIcon
  children: ReactNode
  /** Confirmation shown before the first reveal. Omit to reveal immediately. */
  confirm?: { title: string; body: string; action: string }
  /** Small right-aligned note, e.g. when it was published. */
  meta?: string | undefined
  /** When set, the section is locked (not yet available) and cannot open. */
  lockedNote?: string | undefined
  defaultOpen?: boolean
  className?: string | undefined
}

export function ConsciousDisclosure({
  label,
  icon: Icon,
  children,
  confirm,
  meta,
  lockedNote,
  defaultOpen = false,
  className,
}: ConsciousDisclosureProps) {
  const [open, setOpen] = useState(defaultOpen)
  const [confirming, setConfirming] = useState(false)
  const [revealed, setRevealed] = useState(defaultOpen || !confirm)
  const panelId = useId()

  if (lockedNote) {
    return (
      <div
        className={cn(
          'flex items-center gap-2 rounded-md border border-dashed border-border px-3 py-2 text-small text-muted-foreground',
          className,
        )}
      >
        <Lock aria-hidden="true" className="size-4 shrink-0" />
        <Icon aria-hidden="true" className="size-4 shrink-0" />
        <span className="font-medium text-foreground">{label}</span>
        <span className="ml-auto">{lockedNote}</span>
      </div>
    )
  }

  const toggle = () => {
    if (open) {
      setOpen(false)
    } else if (revealed) {
      setOpen(true)
    } else {
      setConfirming(true)
    }
  }

  const reveal = () => {
    setRevealed(true)
    setConfirming(false)
    setOpen(true)
  }

  return (
    <div className={cn('overflow-hidden rounded-md border border-border bg-surface', className)}>
      <button
        aria-controls={open ? panelId : undefined}
        aria-expanded={open}
        className="flex min-h-(--touch-target) w-full items-center gap-2 px-3 text-left text-small font-medium text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
        onClick={toggle}
        type="button"
      >
        <Icon aria-hidden="true" className="size-4 shrink-0 text-muted-foreground" />
        <span>{label}</span>
        <span className="ml-auto flex items-center gap-2">
          {meta ? (
            <span className="text-caption font-normal text-muted-foreground">{meta}</span>
          ) : null}
          <ChevronDown
            aria-hidden="true"
            className={cn(
              'size-4 shrink-0 text-muted-foreground transition-transform duration-(--duration-fast)',
              open && 'rotate-180',
            )}
          />
        </span>
      </button>

      {confirming && confirm ? (
        <div
          className="border-t border-border bg-surface-subtle px-3 py-2.5 text-small"
          role="group"
        >
          <p className="font-medium text-foreground">{confirm.title}</p>
          <p className="mt-0.5 text-muted-foreground">{confirm.body}</p>
          <div className="mt-2 flex gap-2">
            <Button onClick={reveal} size="sm">
              {confirm.action}
            </Button>
            <Button onClick={() => setConfirming(false)} size="sm" variant="ghost">
              Не сейчас
            </Button>
          </div>
        </div>
      ) : null}

      {open ? (
        <div
          className="border-t border-border px-3 py-3 font-reading text-body leading-relaxed text-foreground"
          id={panelId}
        >
          {children}
        </div>
      ) : null}
    </div>
  )
}

export interface DisclosurePresetProps {
  children: ReactNode
  meta?: string
  lockedNote?: string
  className?: string
}

export function HintDisclosure({ children, meta, lockedNote, className }: DisclosurePresetProps) {
  return (
    <ConsciousDisclosure
      className={className}
      confirm={{
        title: 'Открыть подсказку?',
        body: 'Сначала попробуйте сами — так задача принесёт больше пользы.',
        action: 'Показать подсказку',
      }}
      icon={Lightbulb}
      label="Подсказка"
      lockedNote={lockedNote}
      meta={meta}
    >
      {children}
    </ConsciousDisclosure>
  )
}

export function SolutionDisclosure({
  children,
  meta,
  lockedNote,
  className,
}: DisclosurePresetProps) {
  return (
    <ConsciousDisclosure
      className={className}
      confirm={{
        title: 'Открыть решение?',
        body: 'Решение нельзя «развидеть». Открывайте, только если действительно застряли.',
        action: 'Показать решение',
      }}
      icon={KeyRound}
      label="Решение"
      lockedNote={lockedNote}
      meta={meta}
    >
      {children}
    </ConsciousDisclosure>
  )
}
