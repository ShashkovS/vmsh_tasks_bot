import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { Maximize2, Minus, Plus } from 'lucide-react'
import { useRef, useState, type ReactNode } from 'react'

import type { ReviewAnnotationManifest, ReviewAnnotationMark } from '@vmsh/contracts'
import { Button, Dialog, DialogClose, DialogContent, DialogTitle } from '@vmsh/ui'

import { ReviewAnnotationSurface } from './review-annotation-surface'

export interface ReviewPhotoPreviewProps {
  imageAlt: string
  imageSource: string
  originalHref?: string | undefined
  marks?: ReviewAnnotationMark[]
  rotation?: ReviewAnnotationManifest['rotation']
  children?: (open: () => void) => ReactNode
}

/** docs/review-photo-preview.md: Staff photos share original links and read-only zoom. */
export function ReviewPhotoPreview({
  imageAlt,
  imageSource,
  originalHref,
  marks = [],
  rotation = 0,
  children,
}: ReviewPhotoPreviewProps) {
  const [open, setOpen] = useState(false)
  const [zoom, setZoom] = useState(1)
  const trigger = useRef<HTMLButtonElement>(null)
  const show = () => {
    setZoom(1)
    setOpen(true)
  }
  const originalLink = originalHref ? (
    <a
      className="text-small text-primary underline"
      href={originalHref}
      target="_blank"
      rel="noopener noreferrer"
    >
      <Trans>Открыть оригинал</Trans>
    </a>
  ) : null

  return (
    <div className="space-y-1">
      {children ? (
        children(show)
      ) : (
        <ReviewAnnotationSurface
          className="max-h-[70vh]"
          imageAlt={imageAlt}
          imageSource={imageSource}
          marks={marks}
          rotation={rotation}
          zoom={1}
          onImageClick={show}
        />
      )}
      <div className="flex flex-wrap items-center gap-2">
        <Button ref={trigger} size="sm" variant="outline" type="button" onClick={show}>
          <Maximize2 aria-hidden="true" />
          <Trans>На весь экран</Trans>
        </Button>
        {originalLink}
      </div>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent
          className="h-dvh max-h-dvh w-screen max-w-none grid-rows-[auto_minmax(0,1fr)_auto] rounded-none sm:max-w-none"
          showCloseButton={false}
          finalFocus={trigger}
        >
          <div className="flex items-center justify-between gap-2">
            <DialogTitle>{imageAlt}</DialogTitle>
            <DialogClose render={<Button variant="outline" type="button" />}>
              <Trans>Закрыть</Trans>
            </DialogClose>
          </div>
          <ReviewAnnotationSurface
            className="h-full min-h-0"
            fitToViewport
            imageAlt={imageAlt}
            imageSource={imageSource}
            marks={marks}
            rotation={rotation}
            zoom={zoom}
            testId="review-photo-preview-canvas"
          />
          <div className="flex flex-wrap items-center gap-2">
            <Button
              aria-label={t`Уменьшить масштаб`}
              disabled={zoom <= 0.25}
              onClick={() => setZoom((value) => Math.max(0.25, value - 0.25))}
              type="button"
              variant="outline"
              size="icon"
            >
              <Minus aria-hidden="true" />
            </Button>
            <Button
              aria-label={t`Увеличить масштаб`}
              disabled={zoom >= 4}
              onClick={() => setZoom((value) => Math.min(4, value + 0.25))}
              type="button"
              variant="outline"
              size="icon"
            >
              <Plus aria-hidden="true" />
            </Button>
            <Button onClick={() => setZoom(1)} type="button" variant="outline">
              <Trans>Вписать</Trans>
            </Button>
            <span className="font-num text-caption">{Math.round(zoom * 100)}%</span>
            {originalLink}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
