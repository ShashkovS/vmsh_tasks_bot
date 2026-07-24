import { Maximize2, Minus, Plus } from 'lucide-react'
import { useState, type ReactNode } from 'react'

import { Button, cn } from '@vmsh/ui'

/*
 * A figure (TikZ/SVG output) that can be enlarged. Zoom in / out / reset are
 * keyboard-operable buttons; the enlarged content scrolls locally. The region
 * carries a text alternative (alt); the caption is separate, visible prose.
 */
const MIN = 1
const MAX = 3
const STEP = 0.5

export interface ZoomableFigureProps {
  children: ReactNode
  alt: string
  caption?: ReactNode
  className?: string
}

export function ZoomableFigure({ children, alt, caption, className }: ZoomableFigureProps) {
  const [zoom, setZoom] = useState(1)
  const clamp = (value: number) => Math.min(MAX, Math.max(MIN, Math.round(value * 100) / 100))

  return (
    <figure className={cn('space-y-1.5', className)}>
      <div
        aria-label={alt}
        className="max-h-96 overflow-auto rounded-md border border-paper-edge bg-paper p-2"
        role="img"
      >
        <div
          className="origin-top-left transition-transform duration-(--duration-normal) ease-(--ease-standard)"
          style={{ transform: `scale(${zoom})`, width: zoom > 1 ? `${zoom * 100}%` : undefined }}
        >
          {children}
        </div>
      </div>

      <div className="flex items-center gap-1">
        <Button
          aria-label="Уменьшить"
          disabled={zoom <= MIN}
          onClick={() => setZoom((value) => clamp(value - STEP))}
          size="icon-sm"
          variant="outline"
        >
          <Minus aria-hidden="true" />
        </Button>
        <Button
          aria-label="Увеличить"
          disabled={zoom >= MAX}
          onClick={() => setZoom((value) => clamp(value + STEP))}
          size="icon-sm"
          variant="outline"
        >
          <Plus aria-hidden="true" />
        </Button>
        <Button
          aria-label="Сбросить масштаб"
          disabled={zoom === 1}
          onClick={() => setZoom(1)}
          size="icon-sm"
          variant="ghost"
        >
          <Maximize2 aria-hidden="true" />
        </Button>
        <span className="font-num text-caption text-muted-foreground" data-testid="zoom-value">
          {Math.round(zoom * 100)}%
        </span>
      </div>

      {caption ? (
        <figcaption className="text-label text-muted-foreground">{caption}</figcaption>
      ) : null}
    </figure>
  )
}
