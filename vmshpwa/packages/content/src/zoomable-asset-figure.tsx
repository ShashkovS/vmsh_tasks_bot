import {
  useCallback,
  useRef,
  useState,
  type KeyboardEvent,
  type PointerEvent,
  type ReactNode,
} from 'react'

import type { WebFigureAvailableAsset } from '@vmsh/contracts'

const MINIMUM_ZOOM = 1
const MAXIMUM_ZOOM = 4
const ZOOM_STEP = 0.5

interface Point {
  x: number
  y: number
}

export interface ZoomableAssetFigureProps {
  asset: WebFigureAvailableAsset
  alt: string
  caption?: ReactNode
  className?: string
}

function clampZoom(value: number): number {
  return Math.min(MAXIMUM_ZOOM, Math.max(MINIMUM_ZOOM, Math.round(value * 100) / 100))
}

function distance(first: Point, second: Point): number {
  return Math.hypot(second.x - first.x, second.y - first.y)
}

function midpoint(first: Point, second: Point): Point {
  return { x: (first.x + second.x) / 2, y: (first.y + second.y) / 2 }
}

/**
 * External SVG/raster viewer for the Phase-2 web derivative. Zoom and pan are
 * local viewer state; the framed canvas and its image share one transform.
 */
export function ZoomableAssetFigure({ asset, alt, caption, className }: ZoomableAssetFigureProps) {
  const viewportRef = useRef<HTMLDivElement>(null)
  const pointersRef = useRef(new Map<number, Point>())
  const lastPinchRef = useRef<{ distance: number; midpoint: Point } | null>(null)
  const zoomRef = useRef(MINIMUM_ZOOM)
  const offsetRef = useRef<Point>({ x: 0, y: 0 })
  const [zoom, setZoom] = useState(MINIMUM_ZOOM)
  const [offset, setOffset] = useState<Point>({ x: 0, y: 0 })
  const [failedSource, setFailedSource] = useState<string | null>(null)
  const imageFailed = failedSource === asset.src

  const commitTransform = useCallback((nextZoom: number, nextOffset: Point) => {
    const normalizedZoom = clampZoom(nextZoom)
    const normalizedOffset = normalizedZoom === MINIMUM_ZOOM ? { x: 0, y: 0 } : nextOffset
    zoomRef.current = normalizedZoom
    offsetRef.current = normalizedOffset
    setZoom(normalizedZoom)
    setOffset(normalizedOffset)
  }, [])

  const zoomAround = useCallback(
    (requestedZoom: number, focalPoint?: Point) => {
      const nextZoom = clampZoom(requestedZoom)
      const previousZoom = zoomRef.current
      if (nextZoom === previousZoom) return
      const viewport = viewportRef.current
      const focal =
        focalPoint ??
        (viewport ? { x: viewport.clientWidth / 2, y: viewport.clientHeight / 2 } : { x: 0, y: 0 })
      const ratio = nextZoom / previousZoom
      commitTransform(nextZoom, {
        x: focal.x - (focal.x - offsetRef.current.x) * ratio,
        y: focal.y - (focal.y - offsetRef.current.y) * ratio,
      })
    },
    [commitTransform],
  )

  const reset = useCallback(() => {
    commitTransform(MINIMUM_ZOOM, { x: 0, y: 0 })
  }, [commitTransform])

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === '+' || event.key === '=') {
      event.preventDefault()
      zoomAround(zoomRef.current + ZOOM_STEP)
    } else if (event.key === '-') {
      event.preventDefault()
      zoomAround(zoomRef.current - ZOOM_STEP)
    } else if (event.key === '0') {
      event.preventDefault()
      reset()
    }
  }

  function handlePointerDown(event: PointerEvent<HTMLDivElement>) {
    pointersRef.current.set(event.pointerId, { x: event.clientX, y: event.clientY })
    try {
      event.currentTarget.setPointerCapture?.(event.pointerId)
    } catch {
      // Synthetic browser interaction tests do not create a native active pointer.
    }
    if (pointersRef.current.size === 2) {
      const [first, second] = [...pointersRef.current.values()]
      if (first && second) {
        lastPinchRef.current = {
          distance: distance(first, second),
          midpoint: midpoint(first, second),
        }
      }
    }
  }

  function handlePointerMove(event: PointerEvent<HTMLDivElement>) {
    const previous = pointersRef.current.get(event.pointerId)
    if (!previous) return
    const current = { x: event.clientX, y: event.clientY }
    pointersRef.current.set(event.pointerId, current)

    if (pointersRef.current.size >= 2) {
      const [first, second] = [...pointersRef.current.values()]
      const lastPinch = lastPinchRef.current
      if (!first || !second || !lastPinch || lastPinch.distance === 0) return
      const nextDistance = distance(first, second)
      const nextMidpoint = midpoint(first, second)
      const nextZoom = clampZoom(zoomRef.current * (nextDistance / lastPinch.distance))
      const ratio = nextZoom / zoomRef.current
      commitTransform(nextZoom, {
        x: nextMidpoint.x - (lastPinch.midpoint.x - offsetRef.current.x) * ratio,
        y: nextMidpoint.y - (lastPinch.midpoint.y - offsetRef.current.y) * ratio,
      })
      lastPinchRef.current = { distance: nextDistance, midpoint: nextMidpoint }
      return
    }

    if (zoomRef.current > MINIMUM_ZOOM) {
      commitTransform(zoomRef.current, {
        x: offsetRef.current.x + current.x - previous.x,
        y: offsetRef.current.y + current.y - previous.y,
      })
    }
  }

  function releasePointer(event: PointerEvent<HTMLDivElement>) {
    pointersRef.current.delete(event.pointerId)
    lastPinchRef.current = null
    if (event.currentTarget.hasPointerCapture?.(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
  }

  /* eslint-disable jsx-a11y/no-noninteractive-element-interactions, jsx-a11y/no-noninteractive-tabindex -- The labelled figure region must be focusable for +/-/0 and owns pointer pinch/pan; the actual commands remain native buttons. */
  return (
    <figure className={['vmsh-asset-figure', className].filter(Boolean).join(' ')}>
      <div
        aria-label="Просмотр рисунка. Плюс и минус меняют масштаб, ноль сбрасывает."
        className="vmsh-figure-viewport"
        data-testid="figure-viewport"
        onKeyDown={handleKeyDown}
        onPointerCancel={releasePointer}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={releasePointer}
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
            style={{
              aspectRatio: `${asset.width} / ${asset.height}`,
              transform: `translate3d(${offset.x}px, ${offset.y}px, 0) scale(${zoom})`,
            }}
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
          onClick={() => zoomAround(zoomRef.current - ZOOM_STEP)}
          type="button"
        >
          −
        </button>
        <button
          aria-label="Увеличить рисунок"
          disabled={zoom >= MAXIMUM_ZOOM || imageFailed}
          onClick={() => zoomAround(zoomRef.current + ZOOM_STEP)}
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
