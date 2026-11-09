import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import {
  useContext,
  useEffect,
  useRef,
  useMemo,
  useState,
  type CSSProperties,
  type KeyboardEvent,
  type ReactNode,
} from 'react'

import type { FigurePlacement, WebFigureAvailableAsset } from '@vmsh/contracts'

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
  widthRem?: number
  placement?: FigurePlacement
  tools?: ReactNode
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
 * Shared responsive image canvas. Staff injects occurrence-scoped controls;
 * readers change only local scale. The optional legacy scale callback remains
 * compatible; see docs/figure-layout.md and Staff FigureLayoutEditor.
 */
export function ZoomableAssetFigure({
  asset,
  alt,
  caption,
  className,
  floatHint,
  widthHint,
  scale,
  widthRem,
  placement,
  tools,
  onScaleCycle,
}: ZoomableAssetFigureProps) {
  const imageLoading = useContext(FigureLoadingContext)
  const figureRef = useRef<HTMLElement>(null)
  const [space, setSpace] = useState({ width: 0, figureWidth: 0, rem: 16 })
  useEffect(() => {
    const figure = figureRef.current
    const parent = figure?.parentElement
    if (!parent) return
    const measure = () => {
      const style = getComputedStyle(parent)
      setSpace({
        width: Math.max(
          0,
          parent.clientWidth -
            (Number.parseFloat(style.paddingLeft) || 0) -
            (Number.parseFloat(style.paddingRight) || 0),
        ),
        figureWidth: figure.getBoundingClientRect().width,
        rem: Number.parseFloat(getComputedStyle(document.documentElement).fontSize) || 16,
      })
    }
    measure()
    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(measure)
    observer.observe(parent)
    observer.observe(figure)
    return () => observer.disconnect()
  }, [])
  const [studentScale, setStudentScale] = useState<number>()
  const [failedSource, setFailedSource] = useState<string | null>(null)
  const savedScale = widthRem === undefined ? normalizedScale(scale) : 1
  const displayedScale = studentScale ?? savedScale
  const imageFailed = failedSource === asset.src
  // Explicit editor placement is container-aware, including nested parts.
  // Legacy source hints retain their original behavior; docs/figure-layout.md.
  const floats = useMemo(() => {
    if (placement?.startsWith('float-')) {
      const desired =
        widthRem === undefined
          ? widthHint?.endsWith('%')
            ? (Number.parseFloat(widthHint) / 100) * space.width * displayedScale
            : widthHint?.endsWith('px')
              ? Number.parseFloat(widthHint) * displayedScale
              : space.width * displayedScale
          : widthRem * space.rem * displayedScale
      return (
        space.width >= 32 * space.rem &&
        space.width - Math.min(desired, space.width) - 1.25 * space.rem >= 16 * space.rem
      )
    }
    return placement?.startsWith('center-') ? false : canFloat(floatHint, widthHint, displayedScale)
  }, [placement, floatHint, widthHint, widthRem, displayedScale, space])
  const centered = placement?.startsWith('center-') || (placement?.startsWith('float-') && !floats)
  const small =
    widthRem === undefined
      ? space.figureWidth > 0 && space.figureWidth < 6 * space.rem
      : Math.min(widthRem * space.rem * displayedScale, space.width || Infinity) < 6 * space.rem

  const cycleScale = () => {
    if (imageFailed || tools) return
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
    ? t`Нажмите, чтобы сохранить следующий размер рисунка: ${Math.round(displayedScale * 100)}%.`
    : t`Нажмите, чтобы изменить размер рисунка: ${Math.round(displayedScale * 100)}%.`

  return (
    <figure
      ref={figureRef}
      className={['vmsh-asset-figure', className].filter(Boolean).join(' ')}
      data-placement={placement}
      data-centered={centered || undefined}
      data-editor-small={small || undefined}
      data-float-hint={floats ? floatHint : undefined}
      data-testid="asset-figure"
      style={
        {
          '--vmsh-source-width': widthRem === undefined ? (widthHint ?? '100%') : `${widthRem}rem`,
          '--vmsh-figure-scale': String(displayedScale),
          '--vmsh-print-figure-scale': String(savedScale),
        } as CSSProperties
      }
    >
      <div className="vmsh-figure-image">
        <div
          aria-label={instruction}
          className="vmsh-figure-canvas"
          data-testid="figure-canvas"
          onClick={tools ? undefined : cycleScale}
          onKeyDown={tools ? undefined : handleKeyDown}
          role={tools ? undefined : 'button'}
          tabIndex={tools ? undefined : 0}
          data-editing={tools ? true : undefined}
        >
          {imageFailed ? (
            <div className="vmsh-figure-missing" role="status">
              <strong>
                <Trans>Рисунок недоступен.</Trans>
              </strong>
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
        {tools ? <div className="vmsh-figure-tools">{tools}</div> : null}
      </div>
      {caption ? <figcaption>{caption}</figcaption> : null}
    </figure>
  )
}
