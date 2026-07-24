import { AlertTriangle, RefreshCw, Wifi, WifiOff } from 'lucide-react'

import { Alert, AlertContent, AlertDescription, AlertTitle, Button, cn } from '@vmsh/ui'

/*
 * Connection state surface. Online is unobtrusive — never a persistent, loud
 * banner. Offline/reconnecting say what it means for the action at hand. A
 * conflict is not a disappearing toast: it stays until resolved.
 */
export type ConnectionState = 'online' | 'offline' | 'reconnecting' | 'syncing' | 'conflict'

export interface ConnectionBannerProps {
  state: ConnectionState
  /** What this state means for what the user is doing right now. */
  actionImpact?: string | undefined
  queuedCount?: number | undefined
  onOpenOutbox?: (() => void) | undefined
  onResolve?: (() => void) | undefined
  className?: string | undefined
}

const dotByState: Record<ConnectionState, string> = {
  online: 'bg-connection-online',
  offline: 'bg-connection-offline',
  reconnecting: 'bg-connection-reconnecting',
  syncing: 'bg-connection-syncing',
  conflict: 'bg-connection-conflict',
}

export function ConnectionBanner({
  state,
  actionImpact,
  queuedCount,
  onOpenOutbox,
  onResolve,
  className,
}: ConnectionBannerProps) {
  if (state === 'online' || state === 'syncing') {
    return (
      <p
        className={cn(
          'inline-flex items-center gap-1.5 text-caption text-muted-foreground',
          className,
        )}
        role="status"
      >
        <span aria-hidden="true" className={cn('size-2 rounded-full', dotByState[state])} />
        {state === 'syncing' ? (
          <>
            <RefreshCw
              aria-hidden="true"
              className="size-3.5 animate-spin motion-reduce:animate-none"
            />
            Синхронизация…
          </>
        ) : (
          <>
            <Wifi aria-hidden="true" className="size-3.5" />
            На связи
          </>
        )}
      </p>
    )
  }

  if (state === 'conflict') {
    return (
      <Alert className={className} role="alert" tone="danger">
        <AlertTriangle aria-hidden="true" />
        <AlertContent>
          <AlertTitle>Работа изменилась</AlertTitle>
          <AlertDescription>
            {actionImpact ??
              'Кто-то обновил эту работу. Сравните версии, чтобы ничего не потерять.'}
          </AlertDescription>
          {onResolve ? (
            <div className="mt-2">
              <Button onClick={onResolve} size="sm" variant="outline">
                Разобраться
              </Button>
            </div>
          ) : null}
        </AlertContent>
      </Alert>
    )
  }

  const reconnecting = state === 'reconnecting'
  return (
    <Alert className={className} tone="warning">
      {reconnecting ? (
        <RefreshCw aria-hidden="true" className="animate-spin motion-reduce:animate-none" />
      ) : (
        <WifiOff aria-hidden="true" />
      )}
      <AlertContent>
        <AlertTitle>{reconnecting ? 'Восстанавливаем связь…' : 'Нет сети'}</AlertTitle>
        {actionImpact ? <AlertDescription>{actionImpact}</AlertDescription> : null}
        {queuedCount && queuedCount > 0 ? (
          <div className="mt-2">
            <Button onClick={onOpenOutbox} size="sm" variant="outline">
              В очереди: {queuedCount} — показать
            </Button>
          </div>
        ) : null}
      </AlertContent>
    </Alert>
  )
}
