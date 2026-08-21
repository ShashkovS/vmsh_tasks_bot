import { Maximize2, Minus, Plus } from 'lucide-react'
import { useEffect, useId, useRef, useState, type CSSProperties, type SVGProps } from 'react'

import type {
  ReviewAnnotationColor,
  ReviewAnnotationManifest,
  ReviewAnnotationMark,
} from '@vmsh/contracts'
import { Button, cn } from '@vmsh/ui'

const strokeForColor: Record<ReviewAnnotationColor, string> = {
  red: 'var(--annotation-pen)',
  blue: 'var(--annotation-comment)',
  graphite: 'var(--foreground)',
  amber: 'var(--annotation-highlight)',
}

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
}: ReviewAnnotationSurfaceProps) {
  const [dimensions, setDimensions] = useState({ width: 4, height: 3 })
  const scrollRegionRef = useRef<HTMLDivElement>(null)
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

  return (
    <div
      aria-label="Фотография с разметкой; область можно прокручивать после увеличения"
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
        style={{ aspectRatio: canvasRatio, width: `${zoom * 100}%` }}
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
          <img
            alt={imageAlt}
            className="pointer-events-none absolute inset-0 size-full select-none object-contain"
            draggable={false}
            onLoad={(event) => {
              const image = event.currentTarget
              if (image.naturalWidth && image.naturalHeight) {
                setDimensions({ width: image.naturalWidth, height: image.naturalHeight })
              }
            }}
            src={imageSource}
          />
          <svg
            {...overlayProps}
            className={cn('absolute inset-0 size-full', overlayProps?.className)}
            viewBox="0 0 1 1"
          >
            <ReviewAnnotationMarks arrowMarkerId={markerId} eraserMaskId={maskId} marks={marks} />
          </svg>
        </div>
      </div>
    </div>
  )
}

export interface ReviewAnnotationViewerProps {
  imageAlt: string
  imageSource: string
  manifest: ReviewAnnotationManifest
  className?: string
}

/** Canonical Student/Family read-only rendering of an immutable manifest. */
export function ReviewAnnotationViewer({
  imageAlt,
  imageSource,
  manifest,
  className,
}: ReviewAnnotationViewerProps) {
  const [zoom, setZoom] = useState(NATURAL_ZOOM)
  const textMarks = manifest.marks.filter((mark) => mark.kind === 'text')

  return (
    <figure className={cn('space-y-1', className)}>
      <ReviewAnnotationSurface
        className="max-h-[70vh]"
        imageAlt={imageAlt}
        imageSource={imageSource}
        marks={manifest.marks}
        overlayProps={{ 'aria-hidden': true, className: 'pointer-events-none' }}
        rotation={manifest.rotation}
        testId="review-annotation-viewer-canvas"
        zoom={zoom}
      />
      <div className="flex flex-wrap items-center gap-1">
        <Button
          aria-label="Уменьшить масштаб"
          disabled={zoom <= MINIMUM_ZOOM}
          onClick={() => setZoom((value) => stepZoom(value, -1))}
          size="icon-xs"
          type="button"
          variant="outline"
        >
          <Minus aria-hidden="true" />
        </Button>
        <Button
          aria-label="Увеличить масштаб"
          disabled={zoom >= MAXIMUM_ZOOM}
          onClick={() => setZoom((value) => stepZoom(value, 1))}
          size="icon-xs"
          type="button"
          variant="outline"
        >
          <Plus aria-hidden="true" />
        </Button>
        <Button
          aria-label="Сбросить масштаб"
          disabled={zoom === NATURAL_ZOOM}
          onClick={() => setZoom(NATURAL_ZOOM)}
          size="icon-xs"
          type="button"
          variant="ghost"
        >
          <Maximize2 aria-hidden="true" />
        </Button>
        <figcaption className="text-caption text-muted-foreground">
          Пометки преподавателя · <span className="font-num">{Math.round(zoom * 100)}%</span>
          {zoom > NATURAL_ZOOM ? ' · можно прокрутить' : ''}
        </figcaption>
      </div>
      {textMarks.length > 0 ? (
        <ul className="space-y-1 text-small text-foreground">
          {textMarks.map((mark) => (
            <li className="rounded-md border border-border bg-surface px-2.5 py-1.5" key={mark.markId}>
              {mark.data.text}
            </li>
          ))}
        </ul>
      ) : null}
    </figure>
  )
}

export function ReviewAnnotationMarks({
  arrowMarkerId,
  eraserMaskId,
  marks,
}: {
  arrowMarkerId: string
  eraserMaskId: string
  marks: ReviewAnnotationMark[]
}) {
  const erasers = marks.filter((mark) => mark.kind === 'eraser')
  return (
    <>
      <defs>
        <mask id={eraserMaskId} maskUnits="userSpaceOnUse" x="0" y="0" width="1" height="1">
          <rect fill="white" x="0" y="0" width="1" height="1" />
          {erasers.map((mark) => (
            <path
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
        {marks.map((mark) => {
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
        })}
      </g>
    </>
  )
}
