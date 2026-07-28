import { ImagePlus, Info, WifiOff } from 'lucide-react'
import { useId } from 'react'

import { Alert, AlertContent, AlertDescription, AlertTitle, Button, Textarea, cn } from '@vmsh/ui'

import { AttachmentList, type AttachmentView } from './attachment'
import type { TaskType } from './types'

/*
 * Written-submission composer: text plus up to `maxPhotos` photos, each a page
 * whose order the student controls. Covers draft, offline queue and closed
 * window. Any oral task may also be submitted in writing here.
 */
export interface SubmissionComposerProps {
  taskType: TaskType
  text: string
  onTextChange: (value: string) => void
  attachments: AttachmentView[]
  onAddPhotos?: () => void
  onMoveUp?: (id: string) => void
  onMoveDown?: (id: string) => void
  onRotate?: (id: string) => void
  onRemove?: (id: string) => void
  onRetry?: (id: string) => void
  onSubmit?: () => void
  maxPhotos?: number
  totalSizeLabel?: string
  draftSavedAt?: string
  offline?: boolean
  queued?: boolean
  closed?: boolean
  submitting?: boolean
  className?: string
}

export function SubmissionComposer({
  taskType,
  text,
  onTextChange,
  attachments,
  onAddPhotos,
  onMoveUp,
  onMoveDown,
  onRotate,
  onRemove,
  onRetry,
  onSubmit,
  maxPhotos = 10,
  totalSizeLabel,
  draftSavedAt,
  offline,
  queued,
  closed,
  submitting,
  className,
}: SubmissionComposerProps) {
  const textId = useId()
  const oralNoteId = useId()
  const photosId = useId()

  const empty = text.trim() === '' && attachments.length === 0
  const atLimit = attachments.length >= maxPhotos
  const editingDisabled = closed || queued || submitting

  return (
    <div className={cn('space-y-4', className)}>
      <div className="space-y-1.5">
        <label className="block text-label font-medium text-foreground" htmlFor={textId}>
          Ваше решение
        </label>
        <Textarea
          aria-describedby={taskType === 'oral' ? oralNoteId : undefined}
          className="min-h-32"
          disabled={editingDisabled}
          id={textId}
          onChange={(event) => onTextChange(event.target.value)}
          placeholder="Опишите решение. Формулы можно приложить фотографией."
          value={text}
        />
      </div>

      {taskType === 'oral' ? (
        <Alert tone="info">
          <Info aria-hidden="true" />
          <AlertContent>
            <AlertTitle>Устная задача</AlertTitle>
            <AlertDescription id={oralNoteId}>
              Можно сдать устно в конференции или отправить письменное решение здесь.
            </AlertDescription>
          </AlertContent>
        </Alert>
      ) : null}

      <section aria-labelledby={photosId} className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-label font-medium text-foreground" id={photosId}>
            Фотографии{' '}
            <span className="text-muted-foreground">
              ({attachments.length} из {maxPhotos})
            </span>
          </h2>
          {totalSizeLabel ? (
            <span className="font-num text-caption text-muted-foreground">{totalSizeLabel}</span>
          ) : null}
        </div>

        <AttachmentList
          attachments={attachments}
          disabled={editingDisabled}
          onMoveDown={onMoveDown}
          onMoveUp={onMoveUp}
          onRemove={onRemove}
          onRetry={onRetry}
          onRotate={onRotate}
        />

        <Button
          disabled={editingDisabled || atLimit}
          onClick={onAddPhotos}
          size="sm"
          variant="outline"
        >
          <ImagePlus aria-hidden="true" />
          Добавить фото
        </Button>
        <p className="text-caption text-muted-foreground">
          Камера или файлы · JPG, PNG, HEIC · до {maxPhotos} страниц. Порядок фото — это порядок
          страниц.
        </p>
      </section>

      {offline ? (
        <Alert tone="warning">
          <WifiOff aria-hidden="true" />
          <AlertContent>
            <AlertTitle>Нет сети</AlertTitle>
            <AlertDescription>
              Решение сохранится и отправится автоматически, когда связь вернётся.
            </AlertDescription>
          </AlertContent>
        </Alert>
      ) : null}

      <div className="flex items-center justify-between gap-3">
        <p className="text-caption text-muted-foreground" role="status">
          {draftSavedAt
            ? `Черновик сохранён в ${draftSavedAt}`
            : 'Черновик сохраняется автоматически'}
        </p>
        {closed ? (
          <span className="text-small font-medium text-status-danger">Приём закрыт</span>
        ) : (
          <Button disabled={submitting || queued || empty} onClick={onSubmit} size="lg">
            {queued
              ? 'В очереди'
              : submitting
                ? 'Отправка…'
                : offline
                  ? 'Поставить в очередь'
                  : 'Отправить'}
          </Button>
        )}
      </div>
    </div>
  )
}
