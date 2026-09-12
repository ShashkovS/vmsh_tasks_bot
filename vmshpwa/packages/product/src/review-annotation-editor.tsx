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
import { useId, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'

import {
  reviewAnnotationManifestSchema,
  type ReviewAnnotationColor,
  type ReviewAnnotationManifest,
  type ReviewAnnotationMark,
} from '@vmsh/contracts'
import { Button, Input, Label, cn } from '@vmsh/ui'

import { ReviewAnnotationSurface } from './review-annotation-surface'

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
  const textInputRef = useRef<HTMLInputElement>(null)
  const textControlId = `annotation-text-${useId().replaceAll(':', '')}`

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
          coordinateSpace: 'image',
          kind: 'text',
          data: { ...pendingText.point, text, size: 0.04, color },
        },
      ],
    })
    setPendingText(null)
  }

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

      <ReviewAnnotationSurface
        imageAlt={imageAlt}
        imageSource={imageSource}
        marks={visibleMarks}
        overlayProps={{
          'aria-label': 'Область разметки фотографии',
          className: 'touch-none',
          onPointerCancel: finishGesture,
          onPointerDown: beginGesture,
          onPointerMove: moveGesture,
          onPointerUp: finishGesture,
          role: 'application',
          tabIndex: disabled ? -1 : 0,
        }}
        rotation={document.rotation}
        testId="annotation-canvas"
        zoom={zoom}
      />

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
            <Label htmlFor={textControlId}>Текст пометки</Label>
            <Input
              id={textControlId}
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
      ? {
          markId,
          coordinateSpace: 'image',
          kind: 'pencil',
          data: { points: gesture.points, width: 0.008, color },
        }
      : {
          markId,
          coordinateSpace: 'image',
          kind: 'eraser',
          data: { points: gesture.points, width: 0.025 },
        }
  }
  if (distance(gesture.start, gesture.current) < MIN_GESTURE) return null
  if (gesture.tool === 'arrow') {
    return {
      markId,
      coordinateSpace: 'image',
      kind: 'arrow',
      data: { start: gesture.start, end: gesture.current, width: 0.008, color },
    }
  }
  const box = boxFromPoints(gesture.start, gesture.current)
  if (gesture.tool === 'highlight') {
    return { markId, coordinateSpace: 'image', kind: 'highlight', data: box }
  }
  return {
    markId,
    coordinateSpace: 'image',
    kind: 'rectangle',
    data: { ...box, strokeWidth: 0.008, color },
  }
}
