import { scaleLinear } from '@visx/scale'

import { cn } from '@vmsh/ui'

/*
 * Small, calm progress charts. Every chart is shape-first (never colour-alone)
 * and ships a text/table equivalent. Scales come from visx; the light stats
 * (mean, deviation, quantiles, a Gaussian KDE for the violin) are computed here
 * to keep the dependency surface small.
 */
type Scale = (value: number) => number

function mean(xs: number[]): number {
  return xs.reduce((sum, x) => sum + x, 0) / xs.length
}

function stdDev(xs: number[]): number {
  const m = mean(xs)
  return Math.sqrt(xs.reduce((sum, x) => sum + (x - m) ** 2, 0) / xs.length)
}

function quantileSorted(sorted: number[], q: number): number {
  const pos = (sorted.length - 1) * q
  const base = Math.floor(pos)
  const rest = pos - base
  const lower = sorted[base]!
  const upper = sorted[base + 1]
  return upper === undefined ? lower : lower + rest * (upper - lower)
}

function gaussian(u: number): number {
  return Math.exp(-0.5 * u * u) / Math.sqrt(2 * Math.PI)
}

function kde(values: number[], x: number, h: number): number {
  return values.reduce((sum, xi) => sum + gaussian((x - xi) / h), 0) / (values.length * h)
}

function buildViolinPath(
  ys: number[],
  densities: number[],
  yScale: Scale,
  halfScale: Scale,
  cx: number,
): string {
  const right = ys
    .map(
      (y, i) =>
        `${i ? 'L' : 'M'} ${(cx + halfScale(densities[i]!)).toFixed(1)} ${yScale(y).toFixed(1)}`,
    )
    .join(' ')
  const left = ys
    .map((y, i) => ({ y, i }))
    .reverse()
    .map(({ y, i }) => `L ${(cx - halfScale(densities[i]!)).toFixed(1)} ${yScale(y).toFixed(1)}`)
    .join(' ')
  return `${right} ${left} Z`
}

export interface DistributionViolinProps {
  values: number[]
  self?: number | undefined
  domain?: [number, number] | undefined
  width?: number | undefined
  height?: number | undefined
  caption?: string | undefined
  className?: string | undefined
}

export function DistributionViolin({
  values,
  self,
  domain,
  width = 220,
  height = 200,
  caption,
  className,
}: DistributionViolinProps) {
  const pad = 12
  const sorted = [...values].sort((a, b) => a - b)
  const lo = domain?.[0] ?? sorted[0] ?? 0
  const hi = domain?.[1] ?? sorted[sorted.length - 1] ?? 1
  const bandwidth = 1.06 * stdDev(values) * values.length ** (-1 / 5) || 1

  const samples = 48
  const ys = Array.from({ length: samples }, (_, i) => lo + ((hi - lo) * i) / (samples - 1))
  const densities = ys.map((y) => kde(values, y, bandwidth))
  const maxDensity = Math.max(...densities, 1e-9)

  const yScale = scaleLinear({ domain: [lo, hi], range: [height - pad, pad] })
  const halfScale = scaleLinear({ domain: [0, maxDensity], range: [0, (width - 2 * pad) / 2] })
  const cx = width / 2

  const median = quantileSorted(sorted, 0.5)
  const q1 = quantileSorted(sorted, 0.25)
  const q3 = quantileSorted(sorted, 0.75)
  const selfPos =
    self === undefined
      ? null
      : self > q3
        ? 'выше большинства'
        : self >= median
          ? 'выше среднего'
          : self >= q1
            ? 'около среднего'
            : 'ниже среднего'

  const label = `Распределение по группе. Медиана ${median.toFixed(1)}, разброс от ${q1.toFixed(1)} до ${q3.toFixed(1)}${
    self !== undefined ? `. Твой результат ${self} — ${selfPos}` : ''
  }.`

  return (
    <figure className={cn('space-y-1', className)}>
      <svg
        aria-label={label}
        className="h-auto w-full max-w-[220px]"
        role="img"
        viewBox={`0 0 ${width} ${height}`}
      >
        <path
          className="fill-chart-1/25 stroke-chart-1"
          d={buildViolinPath(ys, densities, yScale, halfScale, cx)}
          strokeWidth={1.5}
        />
        <line
          className="stroke-chart-1"
          strokeWidth={2}
          x1={cx - halfScale(kde(values, median, bandwidth))}
          x2={cx + halfScale(kde(values, median, bandwidth))}
          y1={yScale(median)}
          y2={yScale(median)}
        />
        {self !== undefined ? (
          <g>
            <line
              className="stroke-foreground"
              strokeDasharray="3 2"
              strokeWidth={1.5}
              x1={pad}
              x2={width - pad}
              y1={yScale(self)}
              y2={yScale(self)}
            />
            <circle className="fill-foreground" cx={cx} cy={yScale(self)} r={3} />
          </g>
        ) : null}
      </svg>
      {caption ? (
        <figcaption className="text-caption text-muted-foreground">{caption}</figcaption>
      ) : null}
      <details className="text-caption text-muted-foreground">
        <summary className="cursor-pointer">Показать числами</summary>
        <table className="mt-1">
          <tbody>
            <tr>
              <td className="pr-3">Медиана</td>
              <td className="font-num">{median.toFixed(1)}</td>
            </tr>
            <tr>
              <td className="pr-3">Разброс (Q1–Q3)</td>
              <td className="font-num">
                {q1.toFixed(1)}–{q3.toFixed(1)}
              </td>
            </tr>
            {self !== undefined ? (
              <tr>
                <td className="pr-3">Твой результат</td>
                <td className="font-num">
                  {self} ({selfPos})
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </details>
    </figure>
  )
}

/* ── Trend with confidence band ─────────────────────────────────────────── */

export interface TrendPoint {
  label: string
  value: number
  lower: number
  upper: number
}

function buildBandPath(points: TrendPoint[], xScale: Scale, yScale: Scale): string {
  const top = points.map(
    (p, i) => `${i ? 'L' : 'M'} ${xScale(i).toFixed(1)} ${yScale(p.upper).toFixed(1)}`,
  )
  const bottom = points
    .map((p, i) => ({ p, i }))
    .reverse()
    .map(({ p, i }) => `L ${xScale(i).toFixed(1)} ${yScale(p.lower).toFixed(1)}`)
  return `${top.join(' ')} ${bottom.join(' ')} Z`
}

function buildLinePath(points: TrendPoint[], xScale: Scale, yScale: Scale): string {
  return points
    .map((p, i) => `${i ? 'L' : 'M'} ${xScale(i).toFixed(1)} ${yScale(p.value).toFixed(1)}`)
    .join(' ')
}

export interface TrendWithBandProps {
  points: TrendPoint[]
  domain?: [number, number]
  width?: number
  height?: number
  caption?: string
  className?: string
}

export function TrendWithBand({
  points,
  domain,
  width = 320,
  height = 200,
  caption,
  className,
}: TrendWithBandProps) {
  const padX = 12
  const padTop = 12
  const padBottom = 24
  const values = points.flatMap((p) => [p.lower, p.upper, p.value])
  const lo = domain?.[0] ?? Math.min(...values)
  const hi = domain?.[1] ?? Math.max(...values)

  const xScale = scaleLinear({
    domain: [0, Math.max(points.length - 1, 1)],
    range: [padX, width - padX],
  })
  const yScale = scaleLinear({ domain: [lo, hi], range: [height - padBottom, padTop] })

  const label = `Динамика: от ${points[0]?.value ?? 0} до ${points[points.length - 1]?.value ?? 0}, с доверительной полосой.`

  return (
    <figure className={cn('space-y-1', className)}>
      <svg
        aria-label={label}
        className="h-auto w-full max-w-[320px]"
        role="img"
        viewBox={`0 0 ${width} ${height}`}
      >
        <path className="fill-chart-2/20" d={buildBandPath(points, xScale, yScale)} />
        <path
          className="fill-none stroke-chart-2"
          d={buildLinePath(points, xScale, yScale)}
          strokeWidth={2}
        />
        {points.map((p, i) => (
          <g key={p.label}>
            <circle className="fill-chart-2" cx={xScale(i)} cy={yScale(p.value)} r={3} />
            <text
              className="fill-muted-foreground text-[10px]"
              textAnchor="middle"
              x={xScale(i)}
              y={height - 8}
            >
              {p.label}
            </text>
          </g>
        ))}
      </svg>
      {caption ? (
        <figcaption className="text-caption text-muted-foreground">{caption}</figcaption>
      ) : null}
      <details className="text-caption text-muted-foreground">
        <summary className="cursor-pointer">Показать числами</summary>
        <table className="mt-1">
          <thead>
            <tr>
              <th className="pr-3 text-left font-medium">Период</th>
              <th className="pr-3 text-left font-medium">Значение</th>
              <th className="text-left font-medium">Полоса</th>
            </tr>
          </thead>
          <tbody>
            {points.map((p) => (
              <tr key={p.label}>
                <td className="pr-3">{p.label}</td>
                <td className="pr-3 font-num">{p.value}</td>
                <td className="font-num">
                  {p.lower}–{p.upper}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  )
}
