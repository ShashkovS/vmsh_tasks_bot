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
  /** Server says this publication was already revealed by this student. */
  initiallyRevealed?: boolean | undefined
  /** Loads and audits the exact material before any child content is shown. */
  onReveal?: (() => void | Promise<void>) | undefined
  defaultOpen?: boolean | undefined
  className?: string | undefined
}

export function ConsciousDisclosure({
  label,
  icon: Icon,
  children,
  confirm,
  meta,
  lockedNote,
  initiallyRevealed = false,
  onReveal,
  defaultOpen = false,
  className,
}: ConsciousDisclosureProps) {
  const [open, setOpen] = useState(defaultOpen && onReveal === undefined)
  const [confirming, setConfirming] = useState(false)
  const [revealed, setRevealed] = useState(defaultOpen || initiallyRevealed || !confirm)
  const [loaded, setLoaded] = useState(onReveal === undefined)
  const [revealing, setRevealing] = useState(false)
  const [revealError, setRevealError] = useState<string | null>(null)
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

  const loadAndOpen = async () => {
    if (!loaded && onReveal) {
      setRevealing(true)
      setRevealError(null)
      try {
        await onReveal()
        setLoaded(true)
      } catch {
        setRevealError('Не удалось открыть материал. Проверьте соединение и повторите попытку.')
        setRevealing(false)
        return
      }
      setRevealing(false)
    }
    setConfirming(false)
    setOpen(true)
  }

  const toggle = () => {
    if (open) {
      setOpen(false)
    } else if (revealed) {
      void loadAndOpen()
    } else {
      setConfirming(true)
    }
  }

  const reveal = () => {
    setRevealed(true)
    setConfirming(false)
    void loadAndOpen()
  }

  return (
    <div className={cn('overflow-hidden rounded-md border border-border bg-surface', className)}>
      <button
        aria-controls={open ? panelId : undefined}
        aria-expanded={open}
        className="flex min-h-(--touch-target) w-full items-center gap-2 px-3 text-left text-small font-medium text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
        onClick={toggle}
        disabled={revealing}
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
            <Button disabled={revealing} onClick={reveal} size="sm">
              {revealing ? 'Открываем…' : confirm.action}
            </Button>
            <Button onClick={() => setConfirming(false)} size="sm" variant="ghost">
              Не сейчас
            </Button>
          </div>
        </div>
      ) : null}

      {revealError ? (
        <div
          className="flex flex-wrap items-center gap-2 border-t border-border bg-destructive/10 px-3 py-2 text-small text-destructive"
          role="alert"
        >
          <span className="min-w-0 flex-1">{revealError}</span>
          <Button onClick={() => void loadAndOpen()} size="sm" variant="outline">
            Повторить
          </Button>
        </div>
      ) : null}

      {open && loaded ? (
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
  meta?: string | undefined
  lockedNote?: string | undefined
  initiallyRevealed?: boolean | undefined
  onReveal?: (() => void | Promise<void>) | undefined
  className?: string | undefined
}

export function HintDisclosure({
  children,
  meta,
  lockedNote,
  initiallyRevealed,
  onReveal,
  className,
}: DisclosurePresetProps) {
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
      initiallyRevealed={initiallyRevealed}
      onReveal={onReveal}
    >
      {children}
    </ConsciousDisclosure>
  )
}

export function SolutionDisclosure({
  children,
  meta,
  lockedNote,
  initiallyRevealed,
  onReveal,
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
      initiallyRevealed={initiallyRevealed}
      onReveal={onReveal}
    >
      {children}
    </ConsciousDisclosure>
  )
}
