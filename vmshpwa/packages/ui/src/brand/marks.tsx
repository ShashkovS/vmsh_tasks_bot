/**
 * ВМШ 179 brand marks (art direction B, accepted 2026-07-23).
 *
 * Repo-native SVG, no bitmap source. The sign, wordmark and product icons all
 * inherit `currentColor` so a single asset works in light/dark, monochrome and
 * one-colour print. Product icons form a family with the sign but never replace
 * a role label. Interface icons are Lucide; these are the only brand SVGs.
 */
import type { SVGProps } from 'react'

export interface MarkProps extends Omit<SVGProps<SVGSVGElement>, 'viewBox' | 'width' | 'height'> {
  size?: number
  title?: string
}

const decorative = { 'aria-hidden': true, focusable: 'false' } as const

/** The «179» sign: a rounded token with a small stalk, number set in the UI sans. */
export function Sign179({ size = 32, title, ...props }: MarkProps) {
  const labelled = title ? { role: 'img', 'aria-label': title } : decorative
  return (
    <svg height={size} viewBox="0 0 32 32" width={size} {...labelled} {...props}>
      <rect
        fill="none"
        height="23"
        rx="6.5"
        stroke="currentColor"
        strokeWidth="2"
        width="27"
        x="2.5"
        y="5.5"
      />
      <path d="M16 5.5V1.5" stroke="currentColor" strokeLinecap="round" strokeWidth="2" />
      <circle cx="16" cy="1.6" fill="currentColor" r="1.4" />
      <text
        fill="currentColor"
        fontFamily="'IBM Plex Sans', system-ui, sans-serif"
        fontSize="13"
        fontWeight="600"
        lengthAdjust="spacingAndGlyphs"
        textAnchor="middle"
        textLength="18.5"
        x="16"
        y="21.5"
      >
        179
      </text>
    </svg>
  )
}

/** Horizontal wordmark «ВМШ 179». */
export function Wordmark({ size = 22, title = 'ВМШ 179', ...props }: MarkProps) {
  return (
    <svg
      height={size}
      role="img"
      viewBox="0 0 118 24"
      width={(size * 118) / 24}
      aria-label={title}
      {...props}
    >
      <text
        fill="currentColor"
        fontFamily="'IBM Plex Sans', system-ui, sans-serif"
        fontSize="18"
        fontWeight="600"
        letterSpacing="-0.2"
        x="0"
        y="18"
      >
        ВМШ
      </text>
      <text
        fill="currentColor"
        fontFamily="'IBM Plex Sans', system-ui, sans-serif"
        fontSize="18"
        fontWeight="400"
        letterSpacing="0.2"
        x="60"
        y="18"
      >
        179
      </text>
    </svg>
  )
}

/** Student: a single sheet with written lines. */
export function IconStudent({ size = 24, title, ...props }: MarkProps) {
  const labelled = title ? { role: 'img', 'aria-label': title } : decorative
  return (
    <svg height={size} viewBox="0 0 24 24" width={size} {...labelled} {...props}>
      <rect
        fill="none"
        height="19"
        rx="4"
        stroke="currentColor"
        strokeWidth="1.75"
        width="17"
        x="3.5"
        y="2.5"
      />
      <path
        d="M7.5 7.5h9M7.5 12h9M7.5 16.5h5.5"
        stroke="currentColor"
        strokeLinecap="round"
        strokeWidth="1.75"
      />
    </svg>
  )
}

/** Family: two figures of different height on one baseline. */
export function IconFamily({ size = 24, title, ...props }: MarkProps) {
  const labelled = title ? { role: 'img', 'aria-label': title } : decorative
  return (
    <svg height={size} viewBox="0 0 24 24" width={size} {...labelled} {...props}>
      <circle cx="8.5" cy="7" fill="none" r="3.2" stroke="currentColor" strokeWidth="1.75" />
      <circle cx="17" cy="11.5" fill="none" r="2.6" stroke="currentColor" strokeWidth="1.75" />
      <path
        d="M3 21c0-3.6 2.5-5.9 5.5-5.9s5.5 2.3 5.5 5.9"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeWidth="1.75"
      />
      <path
        d="M14.6 21c0-2.7 1.6-4.3 3.4-4.3s3.4 1.6 3.4 4.3"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeWidth="1.75"
      />
    </svg>
  )
}

/** Staff: a queue of rows with the current one checked. */
export function IconStaff({ size = 24, title, ...props }: MarkProps) {
  const labelled = title ? { role: 'img', 'aria-label': title } : decorative
  return (
    <svg height={size} viewBox="0 0 24 24" width={size} {...labelled} {...props}>
      <rect
        fill="none"
        height="17"
        rx="4"
        stroke="currentColor"
        strokeWidth="1.75"
        width="19"
        x="2.5"
        y="3.5"
      />
      <path d="M2.5 9.5h19" stroke="currentColor" strokeWidth="1.75" />
      <path d="M8.5 9.5v11" stroke="currentColor" strokeWidth="1.4" />
      <path
        d="M11.8 16.4l2 2 3.7-4"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.75"
      />
    </svg>
  )
}

export const productIcons = {
  student: IconStudent,
  family: IconFamily,
  staff: IconStaff,
} as const
