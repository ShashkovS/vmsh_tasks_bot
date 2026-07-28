import {
  ArrowUpRight,
  Check,
  Eraser,
  Highlighter,
  Maximize2,
  Minus,
  Pencil,
  Plus,
  Redo2,
  RotateCcw,
  RotateCw,
  Square,
  Trash2,
  Type as TypeIcon,
  Undo2,
  X,
} from 'lucide-react'
import {
  useId,
  useRef,
  useState,
  type CSSProperties,
  type PointerEvent as ReactPointerEvent,
} from 'react'

import {
  reviewAnnotationManifestSchema,
  type ReviewAnnotationColor,
  type ReviewAnnotationManifest,
  type ReviewAnnotationMark,
} from '@vmsh/contracts'
import { Button, Input, Label, cn } from '@vmsh/ui'

/**
 * Normalized, non-destructive photo editor for development-plan Phase 6.
 * Product/Review annotation stories cover rotation, local zoom and history;
 * Staff persists only the resulting versioned manifest in its review draft.
 */

type AnnotationTool = 'pencil' | 'eraser' | 'text' | 'arrow' | 'rectangle' | 'highlight'
type Rotation = ReviewAnnotationManifest['rotation']
type Point = { x: number; y: number }

interface EditorDocument {
  rotation: Rotation
  marks: ReviewAnnotationMark[]
}

interface ActiveGesture {
  pointerId: number
  tool: Exclude<AnnotationTool, 'text'>
  start: Point
  points: Point[]
  current: Point
}

interface PendingText {
  point: Point
  value: string
}

export interface ReviewAnnotationEditorProps {
  attachmentId: string
  imageAlt: string
  imageSource: string
  initialManifest?: ReviewAnnotationManifest | null
  disabled?: boolean
  className?: string
  onChange?: (manifest: ReviewAnnotationManifest | null) => void
}

const MIN_ZOOM = 1
const MAX_ZOOM = 3
const ZOOM_STEP = 0.5
const MIN_GESTURE = 0.005

const toolOptions: Array<{
  tool: AnnotationTool
  label: string
  icon: typeof Pencil
}> = [
  { tool: 'pencil', label: 'Карандаш', icon: Pencil },
  { tool: 'eraser', label: 'Ластик', icon: Eraser },
  { tool: 'text', label: 'Текст', icon: TypeIcon },
  { tool: 'arrow', label: 'Стрелка', icon: ArrowUpRight },
  { tool: 'rectangle', label: 'Прямоугольник', icon: Square },
  { tool: 'highlight', label: 'Выделение', icon: Highlighter },
]

const colorOptions: Array<{
  color: ReviewAnnotationColor
  label: string
  className: string
}> = [
  { color: 'red', label: 'Красный', className: 'bg-annotation-pen' },
  { color: 'blue', label: 'Синий', className: 'bg-annotation-comment' },
  { color: 'graphite', label: 'Графитовый', className: 'bg-foreground' },
  { color: 'amber', label: 'Янтарный', className: 'bg-annotation-highlight' },
]

const strokeForColor: Record<ReviewAnnotationColor, string> = {
  red: 'var(--annotation-pen)',
  blue: 'var(--annotation-comment)',
  graphite: 'var(--foreground)',
  amber: 'var(--annotation-highlight)',
}

function nextMarkId(): string {
  return `annotation-${crypto.randomUUID()}`
}

function clamp(value: number): number {
  return Math.max(0, Math.min(1, value))
}

function distance(first: Point, second: Point): number {
  return Math.hypot(first.x - second.x, first.y - second.y)
}

function pointFromEvent(event: ReactPointerEvent<SVGSVGElement>): Point | null {
  const matrix = event.currentTarget.getScreenCTM()
  if (!matrix) return null
  const point = event.currentTarget.createSVGPoint()
  point.x = event.clientX
  point.y = event.clientY
  const normalized = point.matrixTransform(matrix.inverse())
  return { x: clamp(normalized.x), y: clamp(normalized.y) }
}

function boxFromPoints(start: Point, end: Point) {
  return {
    x: Math.min(start.x, end.x),
    y: Math.min(start.y, end.y),
    width: Math.abs(start.x - end.x),
    height: Math.abs(start.y - end.y),
  }
}

function pathFromPoints(points: Point[]): string {
  return points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`).join(' ')
}

function rotate(rotation: Rotation, direction: -1 | 1): Rotation {
  const values: Rotation[] = [0, 90, 180, 270]
  const index = values.indexOf(rotation)
  return values[(index + direction + values.length) % values.length]!
}

function documentFromManifest(
  attachmentId: string,
  manifest?: ReviewAnnotationManifest | null,
): EditorDocument {
  if (!manifest || manifest.attachmentId !== attachmentId) return { rotation: 0, marks: [] }
  const parsed = reviewAnnotationManifestSchema.safeParse(manifest)
  return parsed.success
    ? { rotation: parsed.data.rotation, marks: parsed.data.marks }
    : { rotation: 0, marks: [] }
}

export function ReviewAnnotationEditor({
  attachmentId,
  imageAlt,
  imageSource,
  initialManifest,
  disabled = false,
  className,
  onChange,
}: ReviewAnnotationEditorProps) {
  const [document, setDocument] = useState<EditorDocument>(() =>
    documentFromManifest(attachmentId, initialManifest),
  )
  const [past, setPast] = useState<EditorDocument[]>([])
  const [future, setFuture] = useState<EditorDocument[]>([])
  const [tool, setTool] = useState<AnnotationTool>('pencil')
  const [color, setColor] = useState<ReviewAnnotationColor>('red')
  const [gesture, setGesture] = useState<ActiveGesture | null>(null)
  const [pendingText, setPendingText] = useState<PendingText | null>(null)
  const [zoom, setZoom] = useState(1)
  const [dimensions, setDimensions] = useState({ width: 4, height: 3 })
  const textInputRef = useRef<HTMLInputElement>(null)
  const maskId = `annotation-mask-${useId().replaceAll(':', '')}`
  const markerId = `annotation-arrow-${useId().replaceAll(':', '')}`

  const emit = (next: EditorDocument) => {
    if (next.marks.length === 0) {
      onChange?.(null)
      return
    }
    onChange?.(
      reviewAnnotationManifestSchema.parse({
        attachmentId,
        schemaVersion: 1,
        rotation: next.rotation,
        marks: next.marks,
      }),
    )
  }

  const commit = (next: EditorDocument) => {
    setPast((items) => [...items.slice(-49), document])
    setFuture([])
    setDocument(next)
    emit(next)
  }

  const undo = () => {
    const previous = past.at(-1)
    if (!previous) return
    setPast((items) => items.slice(0, -1))
    setFuture((items) => [document, ...items].slice(0, 50))
    setDocument(previous)
    emit(previous)
  }

  const redo = () => {
    const next = future[0]
    if (!next) return
    setFuture((items) => items.slice(1))
    setPast((items) => [...items.slice(-49), document])
    setDocument(next)
    emit(next)
  }

  const beginGesture = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (disabled) return
    const point = pointFromEvent(event)
    if (!point) return
    if (tool === 'text') {
      setPendingText({ point, value: '' })
      window.setTimeout(() => textInputRef.current?.focus(), 0)
      return
    }
    event.currentTarget.setPointerCapture(event.pointerId)
    setGesture({
      pointerId: event.pointerId,
      tool,
      start: point,
      current: point,
      points: [point],
    })
  }

  const moveGesture = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (!gesture || event.pointerId !== gesture.pointerId) return
    const point = pointFromEvent(event)
    if (!point) return
    setGesture((current) => {
      if (!current) return null
      const points =
        current.tool === 'pencil' || current.tool === 'eraser'
          ? [...current.points, point].slice(-4096)
          : current.points
      return { ...current, current: point, points }
    })
  }

  const finishGesture = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (!gesture || event.pointerId !== gesture.pointerId) return
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
    const finished = gesture
    setGesture(null)
    const mark = markFromGesture(finished, color)
    if (mark) commit({ ...document, marks: [...document.marks, mark] })
  }

  const addText = () => {
    const text = pendingText?.value.trim()
    if (!pendingText || !text) return
    commit({
      ...document,
      marks: [
        ...document.marks,
        {
          markId: nextMarkId(),
          kind: 'text',
          data: { ...pendingText.point, text, size: 0.04, color },
        },
      ],
    })
    setPendingText(null)
  }

  const canvasRatio =
    document.rotation === 90 || document.rotation === 270
      ? dimensions.height / dimensions.width
      : dimensions.width / dimensions.height
  const innerWidth =
    document.rotation === 90 || document.rotation === 270
      ? `${(dimensions.width / dimensions.height) * 100}%`
      : '100%'
  const previewMark = gesture ? markFromGesture(gesture, color, 'annotation-preview') : null
  const visibleMarks = previewMark ? [...document.marks, previewMark] : document.marks

  return (
    <section className={cn('space-y-2', className)} aria-label={`Разметка: ${imageAlt}`}>
      <div
        className="flex flex-wrap items-center gap-1"
        role="toolbar"
        aria-label="Инструменты разметки"
      >
        {toolOptions.map((option) => {
          const Icon = option.icon
          return (
            <Button
              aria-label={option.label}
              aria-pressed={tool === option.tool}
              disabled={disabled}
              key={option.tool}
              onClick={() => setTool(option.tool)}
              size="icon-sm"
              type="button"
              variant={tool === option.tool ? 'secondary' : 'ghost'}
            >
              <Icon aria-hidden="true" />
            </Button>
          )
        })}
        <span aria-hidden="true" className="mx-1 h-5 w-px bg-border" />
        {colorOptions.map((option) => (
          <button
            aria-label={option.label}
            aria-pressed={color === option.color}
            className={cn(
              'grid size-7 place-items-center rounded-md border border-border outline-none focus-visible:ring-2 focus-visible:ring-focus-ring',
              color === option.color &&
                'border-annotation-selection ring-1 ring-annotation-selection',
            )}
            disabled={disabled}
            key={option.color}
            onClick={() => setColor(option.color)}
            type="button"
          >
            <span aria-hidden="true" className={cn('size-3.5 rounded-full', option.className)} />
          </button>
        ))}
        <span aria-hidden="true" className="mx-1 h-5 w-px bg-border" />
        <Button
          aria-label="Отменить"
          disabled={disabled || past.length === 0}
          onClick={undo}
          size="icon-sm"
          type="button"
          variant="ghost"
        >
          <Undo2 aria-hidden="true" />
        </Button>
        <Button
          aria-label="Повторить"
          disabled={disabled || future.length === 0}
          onClick={redo}
          size="icon-sm"
          type="button"
          variant="ghost"
        >
          <Redo2 aria-hidden="true" />
        </Button>
        <Button
          aria-label="Повернуть против часовой стрелки"
          disabled={disabled}
          onClick={() => commit({ ...document, rotation: rotate(document.rotation, -1) })}
          size="icon-sm"
          type="button"
          variant="ghost"
        >
          <RotateCcw aria-hidden="true" />
        </Button>
        <Button
          aria-label="Повернуть по часовой стрелке"
          disabled={disabled}
          onClick={() => commit({ ...document, rotation: rotate(document.rotation, 1) })}
          size="icon-sm"
          type="button"
          variant="ghost"
        >
          <RotateCw aria-hidden="true" />
        </Button>
        <Button
          aria-label="Очистить разметку"
          disabled={disabled || document.marks.length === 0}
          onClick={() => commit({ ...document, marks: [] })}
          size="icon-sm"
          type="button"
          variant="ghost"
        >
          <Trash2 aria-hidden="true" />
        </Button>
      </div>

      <div
        aria-label="Фотография с разметкой; область можно прокручивать после увеличения"
        className="max-w-full overflow-auto rounded-md border border-paper-edge bg-surface-sunken p-2"
        role="region"
      >
        <div
          className="relative mx-auto origin-top-left bg-paper shadow-sm"
          data-rotation={document.rotation}
          data-testid="annotation-canvas"
          data-zoom={zoom}
          style={{ aspectRatio: canvasRatio, width: `${zoom * 100}%` }}
        >
          <div
            className="absolute left-1/2 top-1/2 aspect-(--evidence-ratio) -translate-x-1/2 -translate-y-1/2"
            style={
              {
                '--evidence-ratio': `${dimensions.width} / ${dimensions.height}`,
                rotate: `${document.rotation}deg`,
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
              aria-label="Область разметки фотографии"
              className="absolute inset-0 size-full touch-none"
              onPointerCancel={finishGesture}
              onPointerDown={beginGesture}
              onPointerMove={moveGesture}
              onPointerUp={finishGesture}
              role="application"
              tabIndex={disabled ? -1 : 0}
              viewBox="0 0 1 1"
            >
              <AnnotationMarks
                arrowMarkerId={markerId}
                eraserMaskId={maskId}
                marks={visibleMarks}
              />
            </svg>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-1">
        <Button
          aria-label="Уменьшить масштаб"
          disabled={zoom <= MIN_ZOOM}
          onClick={() => setZoom((value) => Math.max(MIN_ZOOM, value - ZOOM_STEP))}
          size="icon-sm"
          type="button"
          variant="outline"
        >
          <Minus aria-hidden="true" />
        </Button>
        <Button
          aria-label="Увеличить масштаб"
          disabled={zoom >= MAX_ZOOM}
          onClick={() => setZoom((value) => Math.min(MAX_ZOOM, value + ZOOM_STEP))}
          size="icon-sm"
          type="button"
          variant="outline"
        >
          <Plus aria-hidden="true" />
        </Button>
        <Button
          aria-label="Сбросить масштаб"
          disabled={zoom === 1}
          onClick={() => setZoom(1)}
          size="icon-sm"
          type="button"
          variant="ghost"
        >
          <Maximize2 aria-hidden="true" />
        </Button>
        <span className="font-num text-caption text-muted-foreground">
          {Math.round(zoom * 100)}% · {document.rotation}° · {document.marks.length} пометок
        </span>
      </div>

      {pendingText ? (
        <form
          className="flex items-end gap-2 rounded-md border border-border bg-surface p-2"
          onSubmit={(event) => {
            event.preventDefault()
            addText()
          }}
        >
          <div className="min-w-0 flex-1 space-y-1">
            <Label htmlFor={`${maskId}-text`}>Текст пометки</Label>
            <Input
              id={`${maskId}-text`}
              maxLength={500}
              onChange={(event) =>
                setPendingText((current) =>
                  current ? { ...current, value: event.target.value } : null,
                )
              }
              placeholder="Что нужно исправить"
              ref={textInputRef}
              value={pendingText.value}
            />
          </div>
          <Button
            aria-label="Добавить текст"
            disabled={!pendingText.value.trim()}
            size="icon-sm"
            type="submit"
          >
            <Check aria-hidden="true" />
          </Button>
          <Button
            aria-label="Отменить текст"
            onClick={() => setPendingText(null)}
            size="icon-sm"
            type="button"
            variant="ghost"
          >
            <X aria-hidden="true" />
          </Button>
        </form>
      ) : null}
    </section>
  )
}

function markFromGesture(
  gesture: ActiveGesture,
  color: ReviewAnnotationColor,
  markId = nextMarkId(),
): ReviewAnnotationMark | null {
  if (gesture.tool === 'pencil' || gesture.tool === 'eraser') {
    if (
      gesture.points.length < 2 ||
      distance(gesture.points[0]!, gesture.points.at(-1)!) < MIN_GESTURE
    ) {
      return null
    }
    return gesture.tool === 'pencil'
      ? { markId, kind: 'pencil', data: { points: gesture.points, width: 0.008, color } }
      : { markId, kind: 'eraser', data: { points: gesture.points, width: 0.025 } }
  }
  if (distance(gesture.start, gesture.current) < MIN_GESTURE) return null
  if (gesture.tool === 'arrow') {
    return {
      markId,
      kind: 'arrow',
      data: { start: gesture.start, end: gesture.current, width: 0.008, color },
    }
  }
  const box = boxFromPoints(gesture.start, gesture.current)
  if (gesture.tool === 'highlight') {
    return { markId, kind: 'highlight', data: box }
  }
  return {
    markId,
    kind: 'rectangle',
    data: { ...box, strokeWidth: 0.008, color },
  }
}

function AnnotationMarks({
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
