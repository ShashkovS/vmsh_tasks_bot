import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { Maximize2, Minus, Plus } from 'lucide-react'
import { useState } from 'react'
import type { ReviewAnnotationManifest } from '@vmsh/contracts'
import { Button, cn } from '@vmsh/ui'
import { ReviewAnnotationSurface } from './review-annotation-surface'
import { ReviewPhotoPreview } from './review-photo-preview'

/*
 * Reading a checked page needs the same freedom as reading a drawing: a step
 * below the natural width lets a tall page stop dominating the conversation.
 */
const ZOOM_LADDER = [0.25, 0.5, 0.75, 1, 1.5, 2, 3] as const
const NATURAL_ZOOM = 1
const MINIMUM_ZOOM = ZOOM_LADDER[0]
const MAXIMUM_ZOOM = ZOOM_LADDER.at(-1) ?? NATURAL_ZOOM

function stepZoom(current: number, direction: 1 | -1): number {
  const found = ZOOM_LADDER.findIndex((step) => step >= current - 0.001)
  const index = found === -1 ? ZOOM_LADDER.length - 1 : found
  return ZOOM_LADDER[Math.min(ZOOM_LADDER.length - 1, Math.max(0, index + direction))] ?? current
}

export interface ReviewAnnotationViewerProps {
  imageAlt: string
  imageSource: string
  manifest: ReviewAnnotationManifest
  originalHref?: string
  className?: string
}

/** docs/review-photo-preview.md: immutable marks share Staff/Student/Family viewing. */
export function ReviewAnnotationViewer({
  imageAlt,
  imageSource,
  manifest,
  className,
  originalHref,
}: ReviewAnnotationViewerProps) {
  const [zoom, setZoom] = useState(NATURAL_ZOOM)
  const textMarks = manifest.marks.filter((mark) => mark.kind === 'text')

  return (
    <figure className={cn('space-y-1', className)}>
      <ReviewPhotoPreview
        imageAlt={imageAlt}
        imageSource={imageSource}
        originalHref={originalHref}
        marks={manifest.marks}
        rotation={manifest.rotation}
      >
        {(open) => (
          <ReviewAnnotationSurface
            className="max-h-[70vh]"
            imageAlt={imageAlt}
            imageSource={imageSource}
            marks={manifest.marks}
            overlayProps={{ 'aria-hidden': true, className: 'pointer-events-none' }}
            rotation={manifest.rotation}
            testId="review-annotation-viewer-canvas"
            zoom={zoom}
            onImageClick={open}
          />
        )}
      </ReviewPhotoPreview>
      <div className="flex flex-wrap items-center gap-1">
        <Button
          aria-label={t`Уменьшить масштаб`}
          disabled={zoom <= MINIMUM_ZOOM}
          onClick={() => setZoom((value) => stepZoom(value, -1))}
          size="icon-xs"
          type="button"
          variant="outline"
        >
          <Minus aria-hidden="true" />
        </Button>
        <Button
          aria-label={t`Увеличить масштаб`}
          disabled={zoom >= MAXIMUM_ZOOM}
          onClick={() => setZoom((value) => stepZoom(value, 1))}
          size="icon-xs"
          type="button"
          variant="outline"
        >
          <Plus aria-hidden="true" />
        </Button>
        <Button
          aria-label={t`Сбросить масштаб`}
          disabled={zoom === NATURAL_ZOOM}
          onClick={() => setZoom(NATURAL_ZOOM)}
          size="icon-xs"
          type="button"
          variant="ghost"
        >
          <Maximize2 aria-hidden="true" />
        </Button>
        <figcaption className="text-caption text-muted-foreground">
          <Trans>Пометки преподавателя ·</Trans>{' '}
          <span className="font-num">{Math.round(zoom * 100)}%</span>
          {zoom > NATURAL_ZOOM ? t` · можно прокрутить` : ''}
        </figcaption>
      </div>
      {textMarks.length > 0 ? (
        <ul className="space-y-1 text-small text-foreground">
          {textMarks.map((mark) => (
            <li
              className="rounded-md border border-border bg-surface px-2.5 py-1.5"
              key={mark.markId}
            >
              {mark.data.text}
            </li>
          ))}
        </ul>
      ) : null}
    </figure>
  )
}
