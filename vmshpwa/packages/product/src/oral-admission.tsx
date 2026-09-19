import { ExternalLink, Mic2 } from 'lucide-react'

import type { OralWindowJoin, StudentOralWindow } from '@vmsh/contracts'
import { Button, buttonVariants, cn } from '@vmsh/ui'

function timeLabel(value: string, date = true): string {
  return new Intl.DateTimeFormat('ru-RU', {
    ...(date ? { day: 'numeric' as const, month: 'short' as const } : {}),
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

export interface OralAdmissionProps {
  windows: StudentOralWindow[]
  revealedJoin?: OralWindowJoin | null
  joiningWindowId?: string | null
  errorMessage?: string | null
  onRevealJoin?: (windowId: string) => void
  className?: string
}

/** classroom-and-oral-workflow.md: compact optional supplement to written submission. */
export function OralAdmission({
  windows,
  revealedJoin,
  joiningWindowId,
  errorMessage,
  onRevealJoin,
  className,
}: OralAdmissionProps) {
  const visible = windows.filter((window) => window.state === 'open' || window.state === 'upcoming')
  if (!visible.length) return null
  return (
    <section aria-label="Устный приём" className={cn('space-y-1 text-small', className)}>
      {visible.map((window) => {
        const open = window.state === 'open'
        const join = open && revealedJoin?.windowId === window.windowId ? revealedJoin : null
        const sameDay =
          new Date(window.opensAt).toDateString() === new Date(window.closesAt).toDateString()
        return (
          <div key={window.windowId} className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="inline-flex items-center gap-1.5">
              <Mic2 aria-hidden="true" className="size-4 shrink-0 text-primary" />
              <span className={cn(open ? 'font-medium text-foreground' : 'text-muted-foreground')}>
                {open ? 'Устный приём сейчас' : 'Устный приём'}
              </span>
            </span>
            <span className="font-num text-muted-foreground">
              {open
                ? `до ${timeLabel(window.closesAt, !sameDay)}`
                : `${timeLabel(window.opensAt)} — ${timeLabel(window.closesAt, !sameDay)}`}
            </span>
            {join ? (
              <>
                <a
                  className={buttonVariants({ size: 'sm', variant: 'outline' })}
                  href={join.joinUrl}
                  rel="noreferrer"
                  target="_blank"
                >
                  {join.joinLabel}
                  <ExternalLink aria-hidden="true" />
                </a>
                {join.joinCode ? (
                  <span>
                    Код: <code className="font-num">{join.joinCode}</code>
                  </span>
                ) : null}
              </>
            ) : open && window.joinAvailable ? (
              <Button
                size="sm"
                variant="outline"
                disabled={joiningWindowId === window.windowId}
                onClick={() => onRevealJoin?.(window.windowId)}
              >
                {joiningWindowId === window.windowId ? 'Получаем ссылку…' : window.joinLabel}
              </Button>
            ) : null}
          </div>
        )
      })}
      {errorMessage ? (
        <p className="text-destructive" role="alert">
          {errorMessage}
        </p>
      ) : null}
    </section>
  )
}
