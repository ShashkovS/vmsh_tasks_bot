/**
 * Minimal mathematical typography for the phase 1 exploration. It exists to
 * judge type colour, size and rhythm of real formulas — not to replace the
 * KaTeX-based renderer the LaTeX pipeline already produces. Nothing here is an
 * image: every expression stays selectable, copyable and reflowable text.
 */
import type { ReactNode } from 'react'

export function M({
  children,
  upright = false,
  label,
}: {
  children: ReactNode
  upright?: boolean
  label?: string
}) {
  const className = upright ? 'ad-m ad-m--upright' : 'ad-m'
  if (label) {
    return (
      <span aria-label={label} className={className} role="math">
        {children}
      </span>
    )
  }
  return <span className={className}>{children}</span>
}

export function Frac({ numerator, denominator }: { numerator: ReactNode; denominator: ReactNode }) {
  return (
    <span className="ad-frac">
      <span className="ad-frac__num">{numerator}</span>
      <span className="ad-frac__den">{denominator}</span>
    </span>
  )
}

export function MathDisplay({
  children,
  label,
  number,
}: {
  children: ReactNode
  label: string
  number?: string
}) {
  return (
    <span className="ad-display">
      <span className="ad-display__row">
        <span aria-label={label} className="ad-m ad-m--upright" role="math">
          {children}
        </span>
        {number ? (
          <span aria-hidden="true" className="ad-display__no">
            ({number})
          </span>
        ) : null}
      </span>
    </span>
  )
}
