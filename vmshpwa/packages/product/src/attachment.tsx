import { ArrowDown, ArrowUp, ImageIcon, RotateCw, Trash2 } from 'lucide-react'

import { Button, Progress, cn } from '@vmsh/ui'

/*
 * A photo attached to a written submission. Each is a page; order is meaningful
 * and changed with up/down buttons (no drag dependency, keyboard-operable). The
 * original received photo is immutable after submit — this model is the client
 * pre-submit view. State is per file: compression, upload, ready, failed, or
 * queued for when the network returns.
 */
export type AttachmentStatus = 'processing' | 'uploading' | 'ready' | 'failed' | 'queued'

export interface AttachmentView {
  id: string
  name: string
  sizeLabel?: string | undefined
  /** Data/object URL for a thumbnail; a placeholder shows when absent. */
  previewUrl?: string | undefined
  rotation?: 0 | 90 | 180 | 270 | undefined
  status: AttachmentStatus
  /** 0–100 while processing/uploading. */
  progress?: number | undefined
  error?: string | undefined
}

export interface AttachmentItemProps {
  attachment: AttachmentView
  index: number
  count: number
  onMoveUp?: ((id: string) => void) | undefined
  onMoveDown?: ((id: string) => void) | undefined
  onRotate?: ((id: string) => void) | undefined
  onRemove?: ((id: string) => void) | undefined
  onRetry?: ((id: string) => void) | undefined
  disabled?: boolean | undefined
}

function StatusLine({ attachment }: { attachment: AttachmentView }) {
  const page = attachment.name
  switch (attachment.status) {
    case 'processing':
      return (
        <div className="space-y-1">
          <Progress aria-label={`Обработка: ${page}`} value={attachment.progress ?? null} />
          <p className="text-caption text-muted-foreground">Сжатие… {attachment.progress ?? 0}%</p>
        </div>
      )
    case 'uploading':
      return (
        <div className="space-y-1">
          <Progress aria-label={`Загрузка: ${page}`} value={attachment.progress ?? null} />
          <p className="text-caption text-muted-foreground">
            Загрузка… {attachment.progress ?? 0}%
          </p>
        </div>
      )
    case 'ready':
      return <p className="text-caption text-status-success">Готово к отправке</p>
    case 'queued':
      return (
        <p className="text-caption text-muted-foreground">В очереди — уйдёт, когда появится сеть</p>
      )
    case 'failed':
      return (
        <p className="text-caption text-status-danger">
          {attachment.error ?? 'Не удалось загрузить'}
        </p>
      )
  }
}

export function AttachmentItem({
  attachment,
  index,
  count,
  onMoveUp,
  onMoveDown,
  onRotate,
  onRemove,
  onRetry,
  disabled,
}: AttachmentItemProps) {
  const pageLabel = `Страница ${index + 1}`
  return (
    <li className="flex items-start gap-3 rounded-md border border-border bg-surface p-2">
      <div className="relative size-16 shrink-0 overflow-hidden rounded bg-surface-sunken">
        {attachment.previewUrl ? (
          <img
            alt=""
            className="size-full object-cover"
            src={attachment.previewUrl}
            style={
              attachment.rotation ? { transform: `rotate(${attachment.rotation}deg)` } : undefined
            }
          />
        ) : (
          <span className="grid size-full place-items-center text-muted-foreground">
            <ImageIcon aria-hidden="true" className="size-6" />
          </span>
        )}
        <span className="absolute left-1 top-1 rounded bg-surface/90 px-1 font-num text-caption text-foreground ring-1 ring-border">
          {index + 1}
        </span>
      </div>

      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex items-baseline justify-between gap-2">
          <span className="truncate text-small font-medium text-foreground">{attachment.name}</span>
          {attachment.sizeLabel ? (
            <span className="shrink-0 font-num text-caption text-muted-foreground">
              {attachment.sizeLabel}
            </span>
          ) : null}
        </div>
        <StatusLine attachment={attachment} />
        {attachment.status === 'failed' && onRetry ? (
          <Button
            disabled={disabled}
            onClick={() => onRetry(attachment.id)}
            size="xs"
            variant="outline"
          >
            Повторить
          </Button>
        ) : null}
      </div>

      <div className="flex shrink-0 flex-col gap-1">
        <div className="flex gap-1">
          <Button
            aria-label={`${pageLabel}: выше`}
            disabled={disabled || index === 0}
            onClick={() => onMoveUp?.(attachment.id)}
            size="icon-xs"
            variant="ghost"
          >
            <ArrowUp aria-hidden="true" />
          </Button>
          <Button
            aria-label={`${pageLabel}: ниже`}
            disabled={disabled || index === count - 1}
            onClick={() => onMoveDown?.(attachment.id)}
            size="icon-xs"
            variant="ghost"
          >
            <ArrowDown aria-hidden="true" />
          </Button>
        </div>
        <div className="flex gap-1">
          {onRotate ? (
            <Button
              aria-label={`${pageLabel}: повернуть`}
              disabled={disabled}
              onClick={() => onRotate(attachment.id)}
              size="icon-xs"
              variant="ghost"
            >
              <RotateCw aria-hidden="true" />
            </Button>
          ) : null}
          <Button
            aria-label={`${pageLabel}: удалить`}
            disabled={disabled}
            onClick={() => onRemove?.(attachment.id)}
            size="icon-xs"
            variant="ghost"
          >
            <Trash2 aria-hidden="true" />
          </Button>
        </div>
      </div>
    </li>
  )
}

export interface AttachmentListProps extends Omit<
  AttachmentItemProps,
  'attachment' | 'index' | 'count'
> {
  attachments: AttachmentView[]
  className?: string
}

export function AttachmentList({ attachments, className, ...handlers }: AttachmentListProps) {
  if (attachments.length === 0) return null
  return (
    <ol className={cn('space-y-2', className)}>
      {attachments.map((attachment, index) => (
        <AttachmentItem
          attachment={attachment}
          count={attachments.length}
          index={index}
          key={attachment.id}
          {...handlers}
        />
      ))}
    </ol>
  )
}
