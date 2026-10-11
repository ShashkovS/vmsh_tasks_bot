import { t } from '@lingui/core/macro'
import { useEffect, useId, useRef, useState, type CSSProperties, type SVGProps } from 'react'

import type {
  ReviewAnnotationColor,
  ReviewAnnotationManifest,
  ReviewAnnotationMark,
} from '@vmsh/contracts'
import { cn } from '@vmsh/ui'

const strokeForColor: Record<ReviewAnnotationColor, string> = {
  red: 'var(--annotation-pen)',
  blue: 'var(--annotation-comment)',
  graphite: 'var(--foreground)',
  amber: 'var(--annotation-highlight)',
}

function pathFromPoints(points: Array<{ x: number; y: number }>): string {
  return points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`).join(' ')
}

export interface ReviewAnnotationSurfaceProps {
  imageAlt: string
  imageSource: string
  marks: ReviewAnnotationMark[]
  rotation: ReviewAnnotationManifest['rotation']
  zoom: number
  overlayProps?: Omit<SVGProps<SVGSVGElement>, 'viewBox'>
  testId?: string
  /** Extra classes for the scroll region, e.g. a height bound when reading. */
  className?: string
  onImageClick?: (() => void) | undefined
  fitToViewport?: boolean
}

/** One geometry implementation shared by the Staff editor and read-only viewers. */
export function ReviewAnnotationSurface({
  imageAlt,
  imageSource,
  marks,
  rotation,
  zoom,
  overlayProps,
  testId,
  className,
  onImageClick,
  fitToViewport = false,
}: ReviewAnnotationSurfaceProps) {
  const [dimensions, setDimensions] = useState({ width: 4, height: 3 })
  const scrollRegionRef = useRef<HTMLDivElement>(null)
  const [viewport, setViewport] = useState({ width: 0, height: 0 })
  useEffect(() => {
    const region = scrollRegionRef.current
    if (!fitToViewport || !region) return
    const measure = () => setViewport({ width: region.clientWidth, height: region.clientHeight })
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(region)
    return () => observer.disconnect()
  }, [fitToViewport])
  const maskId = `annotation-mask-${useId().replaceAll(':', '')}`
  const markerId = `annotation-arrow-${useId().replaceAll(':', '')}`
  const canvasRatio =
    rotation === 90 || rotation === 270
      ? dimensions.height / dimensions.width
      : dimensions.width / dimensions.height
  const innerWidth =
    rotation === 90 || rotation === 270
      ? `${(dimensions.width / dimensions.height) * 100}%`
      : '100%'

  useEffect(() => {
    if (zoom === 1) scrollRegionRef.current?.scrollTo({ left: 0, top: 0 })
  }, [zoom])

  const image = (
    <img
      alt={imageAlt}
      className={cn(
        'absolute inset-0 size-full select-none object-contain',
        overlayProps?.onPointerDown ? 'pointer-events-none' : onImageClick && 'cursor-zoom-in',
      )}
      draggable={false}
      onLoad={(event) => {
        const image = event.currentTarget
        if (image.naturalWidth && image.naturalHeight) {
          setDimensions({ width: image.naturalWidth, height: image.naturalHeight })
        }
      }}
      src={imageSource}
    />
  )

  return (
    <div
      aria-label={t`${imageAlt}; область можно прокручивать после увеличения`}
      className={cn(
        'max-w-full overflow-auto rounded-md border border-paper-edge bg-surface-sunken p-1',
        className,
      )}
      ref={scrollRegionRef}
      role="region"
      // A zoomed canvas must be keyboard-focusable so its scroll area is reachable.
      // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
      tabIndex={0}
    >
      <div
        className="relative mx-auto origin-top-left bg-paper shadow-sm"
        data-rotation={rotation}
        data-testid={testId}
        data-zoom={zoom}
        style={{
          aspectRatio: canvasRatio,
          width: fitToViewport
            ? `${Math.max(1, Math.min(viewport.width - 10, (viewport.height - 10) * canvasRatio)) * zoom}px`
            : `${zoom * 100}%`,
        }}
      >
        <div
          className="absolute left-1/2 top-1/2 aspect-(--evidence-ratio) -translate-x-1/2 -translate-y-1/2"
          style={
            {
              '--evidence-ratio': `${dimensions.width} / ${dimensions.height}`,
              rotate: `${rotation}deg`,
              width: innerWidth,
            } as CSSProperties
          }
        >
          {onImageClick ? (
            <button
              aria-label={t`Открыть на весь экран: ${imageAlt}`}
              className="absolute inset-0 block size-full cursor-zoom-in border-0 bg-transparent p-0 outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
              type="button"
              onClick={onImageClick}
            >
              {image}
            </button>
          ) : (
            image
          )}

          {marks.some((mark) => mark.coordinateSpace !== 'image') ? (
            <svg
              aria-hidden="true"
              className="pointer-events-none absolute inset-0 size-full"
              data-coordinate-space="legacy"
              viewBox="0 0 1 1"
            >
              <ReviewAnnotationMarks
                arrowMarkerId={`${markerId}-legacy`}
                eraserMaskId={`${maskId}-legacy`}
                marks={marks}
                imageRatio={dimensions.width / dimensions.height}
                coordinateSpace="legacy"
              />
            </svg>
          ) : null}
          <svg
            {...overlayProps}
            className={cn(
              'absolute inset-0 size-full',
              !overlayProps?.onPointerDown && 'pointer-events-none',
              overlayProps?.className,
            )}
            // Unit coordinates cover both image axes; see docs/review-annotation-geometry.md.
            data-coordinate-space="image"
            preserveAspectRatio="none"
            viewBox="0 0 1 1"
          >
            <ReviewAnnotationMarks
              arrowMarkerId={markerId}
              eraserMaskId={maskId}
              marks={marks}
              imageRatio={dimensions.width / dimensions.height}
              coordinateSpace="image"
            />
          </svg>
        </div>
      </div>
    </div>
  )
}

export function ReviewAnnotationMarks({
  arrowMarkerId,
  eraserMaskId,
  marks,
  imageRatio,
  coordinateSpace,
}: {
  arrowMarkerId: string
  eraserMaskId: string
  marks: ReviewAnnotationMark[]
  imageRatio: number
  coordinateSpace: 'image' | 'legacy'
}) {
  // Separate viewports preserve the legacy renderer, including marker sizing.
  // Cross-space erasers are mapped into each viewport without rewriting marks.
  const sx = Math.min(1, 1 / imageRatio)
  const sy = Math.min(1, imageRatio)
  const tx = (1 - sx) / 2
  const ty = (1 - sy) / 2
  const placement = (mark: ReviewAnnotationMark) => {
    const sourceSpace = mark.coordinateSpace ?? 'legacy'
    if (sourceSpace === coordinateSpace) return {}
    return {
      transform:
        coordinateSpace === 'image'
          ? `translate(${tx} ${ty}) scale(${sx} ${sy})`
          : `scale(${1 / sx} ${1 / sy}) translate(${-tx} ${-ty})`,
    }
  }
  const erasers = marks.filter((mark) => mark.kind === 'eraser')
  return (
    <>
      <defs>
        <mask id={eraserMaskId} maskUnits="userSpaceOnUse" x="0" y="0" width="1" height="1">
          <rect fill="white" x="0" y="0" width="1" height="1" />
          {erasers.map((mark) => (
            <path
              {...placement(mark)}
              d={pathFromPoints(mark.data.points)}
              fill="none"
              key={mark.markId}
              stroke="black"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={mark.data.width}
            />
          ))}
        </mask>
        <marker
          id={arrowMarkerId}
          markerHeight="4"
          markerUnits="strokeWidth"
          markerWidth="4"
          orient="auto"
          refX="3.5"
          refY="2"
          viewBox="0 0 4 4"
        >
          <path d="M 0 0 L 4 2 L 0 4 z" fill="context-stroke" />
        </marker>
      </defs>
      <g mask={`url(#${eraserMaskId})`}>
        {marks
          .filter((mark) => (mark.coordinateSpace ?? 'legacy') === coordinateSpace)
          .map((mark) => {
            const render = () => {
              if (mark.kind === 'eraser') return null
              if (mark.kind === 'pencil') {
                return (
                  <path
                    d={pathFromPoints(mark.data.points)}
                    fill="none"
                    key={mark.markId}
                    stroke={strokeForColor[mark.data.color]}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={mark.data.width}
                  />
                )
              }
              if (mark.kind === 'arrow') {
                return (
                  <line
                    key={mark.markId}
                    markerEnd={`url(#${arrowMarkerId})`}
                    stroke={strokeForColor[mark.data.color]}
                    strokeLinecap="round"
                    strokeWidth={mark.data.width}
                    x1={mark.data.start.x}
                    x2={mark.data.end.x}
                    y1={mark.data.start.y}
                    y2={mark.data.end.y}
                  />
                )
              }
              if (mark.kind === 'rectangle') {
                return (
                  <rect
                    fill="none"
                    height={mark.data.height}
                    key={mark.markId}
                    stroke={strokeForColor[mark.data.color]}
                    strokeWidth={mark.data.strokeWidth}
                    width={mark.data.width}
                    x={mark.data.x}
                    y={mark.data.y}
                  />
                )
              }
              if (mark.kind === 'highlight') {
                return (
                  <rect
                    fill="var(--annotation-highlight)"
                    fillOpacity="0.35"
                    height={mark.data.height}
                    key={mark.markId}
                    width={mark.data.width}
                    x={mark.data.x}
                    y={mark.data.y}
                  />
                )
              }
              return (
                <text
                  dominantBaseline="hanging"
                  fill={strokeForColor[mark.data.color]}
                  fontFamily="var(--font-sans)"
                  fontSize={mark.data.size}
                  fontWeight="600"
                  key={mark.markId}
                  x={mark.data.x}
                  y={mark.data.y}
                >
                  {mark.data.text}
                </text>
              )
            }
            return (
              <g key={mark.markId} data-mark-id={mark.markId} {...placement(mark)}>
                {render()}
              </g>
            )
          })}
      </g>
    </>
  )
}
