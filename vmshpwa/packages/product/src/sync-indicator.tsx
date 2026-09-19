import { Check, CloudUpload, RefreshCw } from 'lucide-react'

import { Button, cn } from '@vmsh/ui'

/*
 * Outbox indicator. A queued count is a way into the outbox details, never a
 * dead number. Silent when there is nothing to sync.
 */
export interface SyncIndicatorProps {
  queuedCount: number
  syncing?: boolean
  onOpenOutbox?: () => void
  className?: string
}

export function SyncIndicator({
  queuedCount,
  syncing,
  onOpenOutbox,
  className,
}: SyncIndicatorProps) {
  if (syncing) {
    return (
      <span
        className={cn(
          'inline-flex items-center gap-1.5 text-caption text-muted-foreground',
          className,
        )}
        role="status"
      >
        <RefreshCw
          aria-hidden="true"
          className="size-3.5 animate-spin motion-reduce:animate-none"
        />
        Синхронизация…
      </span>
    )
  }

  if (queuedCount <= 0) {
    return (
      <span
        className={cn(
          'inline-flex items-center gap-1.5 text-caption text-muted-foreground',
          className,
        )}
        role="status"
      >
        <Check aria-hidden="true" className="size-3.5 text-status-success" />
        Всё отправлено
      </span>
    )
  }

  return (
    <Button className={className} onClick={onOpenOutbox} size="sm" variant="outline">
      <CloudUpload aria-hidden="true" />В очереди: {queuedCount}
    </Button>
  )
}
