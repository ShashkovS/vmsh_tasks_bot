import {
  useContext,
  useMemo,
  useState,
  type CSSProperties,
  type KeyboardEvent,
  type ReactNode,
} from 'react'

import type { WebFigureAvailableAsset } from '@vmsh/contracts'

import { FigureLoadingContext } from './figure-loading'

/* The Staff ladder is a persisted editorial choice. Student clicks are an
 * ephemeral reading convenience and intentionally use their own shorter set. */
const STAFF_SCALE_LADDER = [
  1, 1.1, 1.2, 1.3, 1.4, 1.5, 1.75, 2, 2.5, 0.25, 0.5, 0.6, 0.7, 0.8, 0.9,
] as const
const STUDENT_SCALE_LADDER = [1, 1.25, 1.5, 2, 0.5, 0.75] as const

export interface ZoomableAssetFigureProps {
  asset: WebFigureAvailableAsset
  alt: string
  caption?: ReactNode
  className?: string
  floatHint?: 'left' | 'right'
  widthHint?: string
  scale?: number
  onScaleCycle?: (nextScale: number) => void
}

function normalizedScale(scale: number | undefined): number {
  return scale === undefined ? 1 : Math.min(2.5, Math.max(0.25, scale))
}

function nextScale(scale: number, ladder: readonly number[]): number {
  const index = ladder.findIndex((candidate) => Math.abs(candidate - scale) < 0.001)
  return ladder[(index + 1 + ladder.length) % ladder.length] ?? ladder[0] ?? 1
}

function canFloat(
  floatHint: 'left' | 'right' | undefined,
  widthHint: string | undefined,
  scale: number,
) {
  if (floatHint === undefined || widthHint === undefined || !widthHint.endsWith('%')) return false
  const width = Number.parseFloat(widthHint)
  return Number.isFinite(width) && width * scale <= 70
}

/**
 * A figure has no scroll viewport or auxiliary zoom controls. A Staff click
 * writes the next editorial scale; a Student click only changes local reading
 * scale and is never sent to the server.
 */
export function ZoomableAssetFigure({
  asset,
  alt,
  caption,
  className,
  floatHint,
  widthHint,
  scale,
  onScaleCycle,
}: ZoomableAssetFigureProps) {
  const imageLoading = useContext(FigureLoadingContext)
  const [studentScale, setStudentScale] = useState<number>()
  const [failedSource, setFailedSource] = useState<string | null>(null)
  const savedScale = normalizedScale(scale)
  const displayedScale = studentScale ?? savedScale
  const imageFailed = failedSource === asset.src
  const floats = useMemo(
    () => canFloat(floatHint, widthHint, displayedScale),
    [displayedScale, floatHint, widthHint],
  )

  const cycleScale = () => {
    if (imageFailed) return
    if (onScaleCycle) {
      onScaleCycle(nextScale(savedScale, STAFF_SCALE_LADDER))
      return
    }
    setStudentScale((current) => nextScale(current ?? savedScale, STUDENT_SCALE_LADDER))
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'Enter' && event.key !== ' ') return
    event.preventDefault()
    cycleScale()
  }

  const instruction = onScaleCycle
    ? `Нажмите, чтобы сохранить следующий размер рисунка: ${Math.round(displayedScale * 100)}%.`
    : `Нажмите, чтобы изменить размер рисунка: ${Math.round(displayedScale * 100)}%.`

  return (
    <figure
      className={['vmsh-asset-figure', className].filter(Boolean).join(' ')}
      data-float-hint={floats ? floatHint : undefined}
      data-testid="asset-figure"
      style={
        {
          '--vmsh-source-width': widthHint ?? '100%',
          '--vmsh-figure-scale': String(displayedScale),
          '--vmsh-print-figure-scale': String(savedScale),
        } as CSSProperties
      }
    >
      <div
        aria-label={instruction}
        className="vmsh-figure-canvas"
        data-testid="figure-canvas"
        onClick={cycleScale}
        onKeyDown={handleKeyDown}
        role="button"
        tabIndex={0}
      >
        {imageFailed ? (
          <div className="vmsh-figure-missing" role="status">
            <strong>Рисунок недоступен.</strong>
            <span>{alt}</span>
          </div>
        ) : (
          <img
            alt={alt}
            decoding="async"
            draggable={false}
            height={asset.height}
            loading={imageLoading}
            onError={() => setFailedSource(asset.src)}
            src={asset.src}
            width={asset.width}
          />
        )}
      </div>
      {caption ? <figcaption>{caption}</figcaption> : null}
    </figure>
  )
}
