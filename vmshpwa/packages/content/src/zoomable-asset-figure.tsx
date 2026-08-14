import { useCallback, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'

import type { WebFigureAvailableAsset } from '@vmsh/contracts'

const MINIMUM_ZOOM = 1
const MAXIMUM_ZOOM = 4
const ZOOM_STEP = 0.5

export interface ZoomableAssetFigureProps {
  asset: WebFigureAvailableAsset
  alt: string
  caption?: ReactNode
  className?: string
}

function clampZoom(value: number): number {
  return Math.min(MAXIMUM_ZOOM, Math.max(MINIMUM_ZOOM, Math.round(value * 100) / 100))
}

/**
 * A scroll-backed image viewer. The canvas takes its real scaled size, so a
 * zoomed image remains reachable instead of being cropped by a CSS transform.
 */
export function ZoomableAssetFigure({ asset, alt, caption, className }: ZoomableAssetFigureProps) {
  const viewportRef = useRef<HTMLDivElement>(null)
  const [zoom, setZoom] = useState(MINIMUM_ZOOM)
  const [failedSource, setFailedSource] = useState<string | null>(null)
  const imageFailed = failedSource === asset.src

  const changeZoom = useCallback((requestedZoom: number) => {
    const nextZoom = clampZoom(requestedZoom)
    setZoom((currentZoom) => {
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
    setZoom(MINIMUM_ZOOM)
    window.requestAnimationFrame(() => {
      const viewport = viewportRef.current
      if (viewport) viewport.scrollTo({ left: 0, top: 0 })
    })
  }, [])

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === '+' || event.key === '=') {
      event.preventDefault()
      changeZoom(zoom + ZOOM_STEP)
    } else if (event.key === '-') {
      event.preventDefault()
      changeZoom(zoom - ZOOM_STEP)
    } else if (event.key === '0') {
      event.preventDefault()
      reset()
    }
  }

  /* eslint-disable jsx-a11y/no-noninteractive-element-interactions, jsx-a11y/no-noninteractive-tabindex -- The labelled scroll region intentionally receives keyboard zoom controls. */
  return (
    <figure className={['vmsh-asset-figure', className].filter(Boolean).join(' ')}>
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
          onClick={() => changeZoom(zoom - ZOOM_STEP)}
          type="button"
        >
          −
        </button>
        <button
          aria-label="Увеличить рисунок"
          disabled={zoom >= MAXIMUM_ZOOM || imageFailed}
          onClick={() => changeZoom(zoom + ZOOM_STEP)}
          type="button"
        >
          +
        </button>
        <button disabled={zoom === MINIMUM_ZOOM || imageFailed} onClick={reset} type="button">
          Сбросить
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
