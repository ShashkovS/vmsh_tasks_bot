import { useState, type ReactNode } from 'react'

import { cn } from '@vmsh/ui'

/*
 * Read-only view of teacher annotations over the immutable submitted evidence.
 * Pen and highlight marks are decorative; comment pins are numbered buttons that
 * reveal their note. The editor (undo/redo, zoom, page nav) is a Staff surface.
 */
export type AnnotationKind = 'pen' | 'highlight' | 'comment'

export interface AnnotationView {
  id: string
  kind: AnnotationKind
  /** Normalized 0–1 coordinates over the evidence. */
  x: number
  y: number
  w?: number
  h?: number
  note?: string
  author?: string
}

export interface AnnotationOverlayProps {
  children: ReactNode
  annotations: AnnotationView[]
  className?: string
}

export function AnnotationOverlay({ children, annotations, className }: AnnotationOverlayProps) {
  const [openId, setOpenId] = useState<string | null>(null)
  const openComment = annotations.find((annotation) => annotation.id === openId) ?? null
  const commentIds = annotations
    .filter((annotation) => annotation.kind === 'comment')
    .map((annotation) => annotation.id)

  return (
    <div className={cn('space-y-2', className)}>
      <div className="relative overflow-hidden rounded-md border border-paper-edge bg-paper">
        {children}
        {annotations.map((annotation) => {
          if (annotation.kind === 'highlight') {
            return (
              <span
                aria-hidden="true"
                className="pointer-events-none absolute rounded-sm bg-annotation-highlight/40 ring-1 ring-annotation-highlight"
                key={annotation.id}
                style={{
                  left: `${annotation.x * 100}%`,
                  top: `${annotation.y * 100}%`,
                  width: `${(annotation.w ?? 0.1) * 100}%`,
                  height: `${(annotation.h ?? 0.05) * 100}%`,
                }}
              />
            )
          }
          if (annotation.kind === 'pen') {
            return (
              <span
                aria-hidden="true"
                className="pointer-events-none absolute size-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-annotation-pen"
                key={annotation.id}
                style={{ left: `${annotation.x * 100}%`, top: `${annotation.y * 100}%` }}
              />
            )
          }
          const number = commentIds.indexOf(annotation.id) + 1
          const selected = openId === annotation.id
          return (
            <button
              aria-label={`Комментарий ${number}`}
              aria-pressed={selected}
              className="absolute grid size-5 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-annotation-comment font-num text-caption font-semibold text-white ring-2 ring-paper focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
              key={annotation.id}
              onClick={() => setOpenId(selected ? null : annotation.id)}
              style={{ left: `${annotation.x * 100}%`, top: `${annotation.y * 100}%` }}
              type="button"
            >
              {number}
            </button>
          )
        })}
      </div>

      <div className="flex flex-wrap gap-3 text-caption text-muted-foreground">
        <span className="inline-flex items-center gap-1">
          <span aria-hidden="true" className="size-3 rounded-full border-2 border-annotation-pen" />
          перо
        </span>
        <span className="inline-flex items-center gap-1">
          <span aria-hidden="true" className="size-3 rounded-sm bg-annotation-highlight/50" />
          выделение
        </span>
        <span className="inline-flex items-center gap-1">
          <span
            aria-hidden="true"
            className="grid size-3.5 place-items-center rounded-full bg-annotation-comment text-[0.5rem] text-white"
          >
            1
          </span>
          комментарий
        </span>
      </div>

      {openComment?.note ? (
        <div
          aria-label="Комментарий преподавателя"
          className="rounded-md border border-border bg-surface p-3 text-small"
          role="region"
        >
          {openComment.author ? (
            <p className="text-caption font-medium text-foreground">{openComment.author}</p>
          ) : null}
          <p className="text-foreground">{openComment.note}</p>
        </div>
      ) : null}
    </div>
  )
}
