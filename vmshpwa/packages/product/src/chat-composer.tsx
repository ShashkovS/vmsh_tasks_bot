import { Camera, ChevronLeft, ChevronRight, ImagePlus, SendHorizontal, X } from 'lucide-react'
import type { ReactNode } from 'react'

import { Button, cn } from '@vmsh/ui'

import type { AttachmentView } from './attachment'

/*
 * Messenger-shaped composer for the task dialogue: one input row with an
 * attach and a send control, and a strip of pending photos above it. Page order
 * is still explicit and keyboard-operable — the strip keeps the numbered pages
 * of `AttachmentList` without its full-height rows. The input itself is a slot,
 * because a written solution and a typed test answer need different controls.
 * Narrow screens give the input its own row (docs/task-interaction-polish.md).
 */

export interface ChatAttachmentStripProps {
  attachments: AttachmentView[]
  onMoveUp?: ((id: string) => void) | undefined
  onMoveDown?: ((id: string) => void) | undefined
  onRemove?: ((id: string) => void) | undefined
  disabled?: boolean | undefined
  className?: string | undefined
}

const statusLabel: Record<AttachmentView['status'], string> = {
  processing: 'сжимаем',
  uploading: 'загружаем',
  ready: 'готово',
  queued: 'в очереди',
  failed: 'ошибка',
}

export function ChatAttachmentStrip({
  attachments,
  onMoveUp,
  onMoveDown,
  onRemove,
  disabled,
  className,
}: ChatAttachmentStripProps) {
  if (attachments.length === 0) return null
  return (
    <ol className={cn('flex gap-2 overflow-x-auto pb-1', className)}>
      {attachments.map((attachment, index) => {
        const page = `Страница ${index + 1}`
        return (
          <li
            className="relative w-20 shrink-0 space-y-1 rounded-md border border-border bg-surface p-1"
            key={attachment.id}
          >
            <div className="relative aspect-square overflow-hidden rounded bg-surface-sunken">
              {attachment.previewUrl ? (
                <img alt={page} className="size-full object-cover" src={attachment.previewUrl} />
              ) : null}
              <span className="absolute left-0.5 top-0.5 rounded bg-surface/90 px-1 font-num text-caption text-foreground ring-1 ring-border">
                {index + 1}
              </span>
              <Button
                aria-label={`${page}: удалить`}
                className="absolute right-0.5 top-0.5 bg-surface/90"
                disabled={disabled}
                onClick={() => onRemove?.(attachment.id)}
                size="icon-xs"
                variant="ghost"
              >
                <X aria-hidden="true" />
              </Button>
            </div>
            <p
              className={`truncate text-center text-caption ${
                attachment.status === 'failed' ? 'text-danger' : 'text-muted-foreground'
              }`}
            >
              {attachment.status === 'failed'
                ? (attachment.error ?? statusLabel.failed)
                : statusLabel[attachment.status]}
            </p>
            <div className="flex justify-between">
              <Button
                aria-label={`${page}: раньше`}
                disabled={disabled || index === 0}
                onClick={() => onMoveUp?.(attachment.id)}
                size="icon-xs"
                variant="ghost"
              >
                <ChevronLeft aria-hidden="true" />
              </Button>
              <Button
                aria-label={`${page}: позже`}
                disabled={disabled || index === attachments.length - 1}
                onClick={() => onMoveDown?.(attachment.id)}
                size="icon-xs"
                variant="ghost"
              >
                <ChevronRight aria-hidden="true" />
              </Button>
            </div>
          </li>
        )
      })}
    </ol>
  )
}

export interface ChatComposerProps {
  /** The input control: a growing textarea, or a typed answer field. */
  children: ReactNode
  onSend?: () => void
  sendLabel?: string
  sendDisabled?: boolean
  sending?: boolean
  onAttach?: () => void
  attachLabel?: string
  attachDisabled?: boolean
  /** Opens the device camera when the surrounding form supports photo capture. */
  onCapture?: () => void
  captureLabel?: string
  captureDisabled?: boolean
  attachments?: AttachmentView[]
  onMoveAttachmentUp?: (id: string) => void
  onMoveAttachmentDown?: (id: string) => void
  onRemoveAttachment?: (id: string) => void
  attachmentsDisabled?: boolean
  /** Quiet line under the row: photo count, size, offline state. */
  hint?: ReactNode
  className?: string
}

export function ChatComposer({
  children,
  onSend,
  sendLabel = 'Отправить',
  sendDisabled,
  sending,
  onAttach,
  attachLabel = 'Добавить фото',
  attachDisabled,
  onCapture,
  captureLabel = 'Сделать фото',
  captureDisabled,
  attachments = [],
  onMoveAttachmentUp,
  onMoveAttachmentDown,
  onRemoveAttachment,
  attachmentsDisabled,
  hint,
  className,
}: ChatComposerProps) {
  return (
    <div className={cn('space-y-2 font-sans', className)}>
      <ChatAttachmentStrip
        attachments={attachments}
        disabled={attachmentsDisabled}
        onMoveDown={onMoveAttachmentDown}
        onMoveUp={onMoveAttachmentUp}
        onRemove={onRemoveAttachment}
      />
      <div className="flex flex-wrap items-end gap-2">
        {onAttach ? (
          <Button
            aria-label={attachLabel}
            disabled={attachDisabled}
            onClick={onAttach}
            size="icon"
            variant="outline"
          >
            <ImagePlus aria-hidden="true" />
          </Button>
        ) : null}
        {onCapture ? (
          <Button
            aria-label={captureLabel}
            disabled={captureDisabled ?? attachDisabled}
            onClick={onCapture}
            size="icon"
            title={captureLabel}
            variant="outline"
          >
            <Camera aria-hidden="true" />
          </Button>
        ) : null}
        <div className="min-w-0 flex-1 max-sm:order-first max-sm:basis-full">{children}</div>
        <Button
          className="max-sm:ml-auto"
          aria-label={sendLabel}
          disabled={sendDisabled || sending}
          onClick={onSend}
        >
          <SendHorizontal aria-hidden="true" />
          <span className="max-sm:sr-only">{sending ? 'Отправляем…' : sendLabel}</span>
        </Button>
      </div>
      {hint ? <div className="text-caption text-muted-foreground">{hint}</div> : null}
    </div>
  )
}
