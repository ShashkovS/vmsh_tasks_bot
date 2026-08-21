import {
  useCallback,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent,
  type ReactNode,
} from 'react'

import type { WebFigureAvailableAsset } from '@vmsh/contracts'

/*
 * A fixed ladder instead of a step: below the natural width a reader wants
 * finer control (a big drawing should be able to get out of the way), above it
 * coarser jumps are enough.
 */
const ZOOM_LADDER = [0.25, 0.5, 0.75, 1, 1.5, 2, 3, 4] as const
const NATURAL_ZOOM = 1
const MINIMUM_ZOOM = ZOOM_LADDER[0]
const MAXIMUM_ZOOM = ZOOM_LADDER.at(-1) ?? NATURAL_ZOOM

export interface ZoomableAssetFigureProps {
  asset: WebFigureAvailableAsset
  alt: string
  caption?: ReactNode
  className?: string
  floatHint?: 'left' | 'right'
  widthHint?: string
}

function stepZoom(current: number, direction: 1 | -1): number {
  const found = ZOOM_LADDER.findIndex((step) => step >= current - 0.001)
  const index = found === -1 ? ZOOM_LADDER.length - 1 : found
  return ZOOM_LADDER[Math.min(ZOOM_LADDER.length - 1, Math.max(0, index + direction))] ?? current
}

/**
 * A scroll-backed image viewer. The canvas takes its real scaled size, so a
 * zoomed image remains reachable instead of being cropped by a CSS transform.
 */
export function ZoomableAssetFigure({
  asset,
  alt,
  caption,
  className,
  floatHint,
  widthHint,
}: ZoomableAssetFigureProps) {
  const viewportRef = useRef<HTMLDivElement>(null)
  const [zoom, setZoom] = useState(NATURAL_ZOOM)
  const [failedSource, setFailedSource] = useState<string | null>(null)
  const imageFailed = failedSource === asset.src

  const changeZoom = useCallback((direction: 1 | -1) => {
    setZoom((currentZoom) => {
      const nextZoom = stepZoom(currentZoom, direction)
      if (nextZoom === currentZoom) return currentZoom
      const viewport = viewportRef.current
      const horizontalCenter = viewport
        ? (viewport.scrollLeft + viewport.clientWidth / 2) / Math.max(1, viewport.scrollWidth)
        : 0.5
      const verticalCenter = viewport
        ? (viewport.scrollTop + viewport.clientHeight / 2) / Math.max(1, viewport.scrollHeight)
        : 0.5
      window.requestAnimationFrame(() => {
        const current = viewportRef.current
        if (!current) return
        current.scrollLeft = horizontalCenter * current.scrollWidth - current.clientWidth / 2
        current.scrollTop = verticalCenter * current.scrollHeight - current.clientHeight / 2
      })
      return nextZoom
    })
  }, [])

  const reset = useCallback(() => {
    setZoom(NATURAL_ZOOM)
    window.requestAnimationFrame(() => {
      const viewport = viewportRef.current
      if (viewport) viewport.scrollTo({ left: 0, top: 0 })
    })
  }, [])

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === '+' || event.key === '=') {
      event.preventDefault()
      changeZoom(1)
    } else if (event.key === '-') {
      event.preventDefault()
      changeZoom(-1)
    } else if (event.key === '0') {
      event.preventDefault()
      reset()
    }
  }

  /* eslint-disable jsx-a11y/no-noninteractive-element-interactions, jsx-a11y/no-noninteractive-tabindex -- The labelled scroll region intentionally receives keyboard zoom controls. */
  return (
    <figure
      className={['vmsh-asset-figure', className].filter(Boolean).join(' ')}
      data-float-hint={floatHint}
      data-zoomed={zoom > NATURAL_ZOOM ? 'true' : undefined}
      style={widthHint ? ({ '--vmsh-source-width': widthHint } as CSSProperties) : undefined}
    >
      <div
        aria-label="Просмотр рисунка. Плюс и минус меняют масштаб, ноль сбрасывает."
        className="vmsh-figure-viewport"
        data-testid="figure-viewport"
        onKeyDown={handleKeyDown}
        ref={viewportRef}
        role="region"
        tabIndex={0}
      >
        {imageFailed ? (
          <div className="vmsh-figure-missing" role="status">
            <strong>Рисунок недоступен.</strong>
            <span>{alt}</span>
          </div>
        ) : (
          <div
            className="vmsh-figure-canvas"
            data-testid="figure-canvas"
            style={{ width: `min(${zoom * 100}%, ${asset.width * zoom}px)` }}
          >
            <img
              alt={alt}
              decoding="async"
              draggable={false}
              height={asset.height}
              loading="lazy"
              onError={() => setFailedSource(asset.src)}
              src={asset.src}
              width={asset.width}
            />
          </div>
        )}
      </div>

      <div className="vmsh-figure-controls" role="group" aria-label="Масштаб рисунка">
        <button
          aria-label="Уменьшить рисунок"
          disabled={zoom <= MINIMUM_ZOOM || imageFailed}
          onClick={() => changeZoom(-1)}
          type="button"
        >
          −
        </button>
        <button
          aria-label="Увеличить рисунок"
          disabled={zoom >= MAXIMUM_ZOOM || imageFailed}
          onClick={() => changeZoom(1)}
          type="button"
        >
          +
        </button>
        <button
          aria-label="Сбросить масштаб"
          disabled={zoom === NATURAL_ZOOM || imageFailed}
          onClick={reset}
          title="Сбросить масштаб"
          type="button"
        >
          ↺
        </button>
        <output aria-live="polite" data-testid="figure-zoom">
          {Math.round(zoom * 100)}%
        </output>
      </div>

      {caption ? <figcaption>{caption}</figcaption> : null}
    </figure>
  )
  /* eslint-enable jsx-a11y/no-noninteractive-element-interactions, jsx-a11y/no-noninteractive-tabindex */
}
