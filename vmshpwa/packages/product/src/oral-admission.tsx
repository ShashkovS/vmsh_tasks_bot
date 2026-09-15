import { Clock3, ExternalLink, Mic2 } from 'lucide-react'

import type { OralWindowJoin, StudentOralWindow } from '@vmsh/contracts'
import {
  Alert,
  AlertContent,
  AlertDescription,
  Button,
  Card,
  CardContent,
  buttonVariants,
  cn,
} from '@vmsh/ui'

const stateLabel = {
  upcoming: 'Скоро',
  open: 'Открыто',
  closed: 'Завершено',
  cancelled: 'Отменено',
} as const

function timeLabel(value: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'short',
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

/** Student-facing oral windows. Join secrets appear only after an explicit request. */
export function OralAdmission({
  windows,
  revealedJoin,
  joiningWindowId,
  errorMessage,
  onRevealJoin,
  className,
}: OralAdmissionProps) {
  return (
    <section aria-labelledby="oral-admission-title" className={cn('space-y-3', className)}>
      <div className="space-y-0.5">
        <h2
          className="flex items-center gap-2 text-title-sm font-semibold"
          id="oral-admission-title"
        >
          <Mic2 aria-hidden="true" className="size-4 text-primary" />
          Устный приём
        </h2>
        <p className="text-small text-muted-foreground">
          Задачу также можно отправить письменно ниже.
        </p>
      </div>

      {windows.length === 0 ? (
        <Alert tone="info">
          <Clock3 aria-hidden="true" />
          <AlertContent>
            <AlertDescription>
              Для этого занятия окна устного приёма пока не назначены.
            </AlertDescription>
          </AlertContent>
        </Alert>
      ) : (
        <div className="grid gap-2">
          {windows.map((window) => {
            const join = revealedJoin?.windowId === window.windowId ? revealedJoin : null
            return (
              <Card key={window.windowId}>
                <CardContent className="flex flex-col gap-3 py-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">Окно {window.sequenceNumber}</span>
                      <span
                        className={cn(
                          'rounded-md border px-1.5 py-0.5 text-caption font-medium',
                          window.state === 'open'
                            ? 'border-status-success-border bg-status-success-surface text-status-success'
                            : 'border-border text-muted-foreground',
                        )}
                      >
                        {stateLabel[window.state]}
                      </span>
                    </div>
                    <p className="mt-1 font-num text-small text-muted-foreground">
                      {timeLabel(window.opensAt)} — {timeLabel(window.closesAt)}
                    </p>
                    {join?.joinCode ? (
                      <p className="mt-1 text-small">
                        Код: <code className="font-num">{join.joinCode}</code>
                      </p>
                    ) : null}
                  </div>

                  {join ? (
                    <a
                      className={buttonVariants()}
                      href={join.joinUrl}
                      rel="noreferrer"
                      target="_blank"
                    >
                      {join.joinLabel}
                      <ExternalLink aria-hidden="true" />
                    </a>
                  ) : window.joinAvailable ? (
                    <Button
                      disabled={joiningWindowId === window.windowId}
                      onClick={() => onRevealJoin?.(window.windowId)}
                    >
                      {joiningWindowId === window.windowId ? 'Получаем ссылку…' : window.joinLabel}
                    </Button>
                  ) : null}
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}

      {errorMessage ? (
        <p className="text-small text-destructive" role="alert">
          {errorMessage}
        </p>
      ) : null}
    </section>
  )
}
