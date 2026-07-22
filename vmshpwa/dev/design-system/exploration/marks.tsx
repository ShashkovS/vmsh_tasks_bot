/**
 * Repo-native brand exploration for phase 1: one «179» sign, one wordmark and
 * three product icons per direction. Everything inherits `currentColor`, has no
 * bitmap source and is drawn to survive 16 px.
 */
import type { DirectionId } from './directions'

export interface MarkProps {
  size?: number
  className?: string
}

const hidden = { 'aria-hidden': true, focusable: 'false' } as const

/* ---------------------------------------------------------------- signs */

function SignA({ size = 32, className }: MarkProps) {
  return (
    <svg className={className} height={size} viewBox="0 0 32 32" width={size} {...hidden}>
      <rect
        fill="none"
        height="29"
        rx="1.5"
        stroke="currentColor"
        strokeWidth="1.6"
        width="23"
        x="4.5"
        y="1.5"
      />
      <path d="M8 8.5h16" stroke="currentColor" strokeWidth="1.6" />
      <text
        fill="currentColor"
        fontFamily="var(--ad-font-ui)"
        fontSize="12"
        fontWeight="700"
        lengthAdjust="spacingAndGlyphs"
        textAnchor="middle"
        textLength="17"
        x="16"
        y="22.5"
      >
        179
      </text>
    </svg>
  )
}

function SignB({ size = 32, className }: MarkProps) {
  return (
    <svg className={className} height={size} viewBox="0 0 32 32" width={size} {...hidden}>
      <rect
        fill="none"
        height="24"
        rx="7"
        stroke="currentColor"
        strokeWidth="1.8"
        width="28"
        x="2"
        y="4"
      />
      <path d="M16 4V0.8" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" />
      <text
        fill="currentColor"
        fontFamily="var(--ad-font-ui)"
        fontSize="12.5"
        fontWeight="600"
        lengthAdjust="spacingAndGlyphs"
        textAnchor="middle"
        textLength="19"
        x="16"
        y="20.5"
      >
        179
      </text>
    </svg>
  )
}

function SignC({ size = 32, className }: MarkProps) {
  return (
    <svg className={className} height={size} viewBox="0 0 32 32" width={size} {...hidden}>
      <path
        d="M2 6.5h9l2-3.5h17V29H2z"
        fill="none"
        stroke="currentColor"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
      <text
        fill="currentColor"
        fontFamily="var(--ad-font-ui)"
        fontSize="11.5"
        fontWeight="600"
        lengthAdjust="spacingAndGlyphs"
        textAnchor="middle"
        textLength="18"
        x="16.5"
        y="20"
      >
        179
      </text>
      <path d="M7 23.5h19M7 25.8h19" stroke="currentColor" strokeWidth="1.1" />
    </svg>
  )
}

/* ------------------------------------------------------------ wordmarks */

function WordmarkA({ size = 22, className }: MarkProps) {
  return (
    <svg
      className={className}
      height={size}
      role="img"
      viewBox="-2 0 136 24"
      width={(size * 132) / 24}
      aria-label="ВМШ 179"
    >
      <text
        fill="currentColor"
        fontFamily="var(--ad-font-reading)"
        fontSize="19"
        fontWeight="600"
        letterSpacing="0.5"
        x="0"
        y="18"
      >
        ВМШ
      </text>
      <path d="M62 4v16" stroke="currentColor" strokeWidth="1.2" />
      <text
        fill="currentColor"
        fontFamily="var(--ad-font-ui)"
        fontSize="19"
        fontWeight="500"
        letterSpacing="1"
        x="70"
        y="18"
      >
        179
      </text>
    </svg>
  )
}

function WordmarkB({ size = 22, className }: MarkProps) {
  return (
    <svg
      className={className}
      height={size}
      role="img"
      viewBox="-2 0 136 24"
      width={(size * 132) / 24}
      aria-label="ВМШ 179"
    >
      <text
        fill="currentColor"
        fontFamily="var(--ad-font-ui)"
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
        fontFamily="var(--ad-font-ui)"
        fontSize="18"
        fontWeight="400"
        letterSpacing="-0.2"
        x="61"
        y="18"
      >
        179
      </text>
    </svg>
  )
}

function WordmarkC({ size = 22, className }: MarkProps) {
  return (
    <svg
      className={className}
      height={size}
      role="img"
      viewBox="-2 0 136 24"
      width={(size * 132) / 24}
      aria-label="ВМШ 179"
    >
      <text
        fill="currentColor"
        fontFamily="var(--ad-font-reading)"
        fontSize="18"
        fontWeight="700"
        letterSpacing="1.6"
        x="0"
        y="17"
      >
        ВМШ
      </text>
      <text
        fill="currentColor"
        fontFamily="var(--ad-font-reading)"
        fontSize="18"
        fontWeight="400"
        letterSpacing="1.6"
        x="72"
        y="17"
      >
        179
      </text>
      <path d="M0 21.2h126M0 23h126" stroke="currentColor" strokeWidth="0.9" />
    </svg>
  )
}

/* -------------------------------------------------------- product icons */

/** Student: a single sheet with a folded corner and one written line. */
function StudentA({ size = 24, className }: MarkProps) {
  return (
    <svg className={className} height={size} viewBox="0 0 24 24" width={size} {...hidden}>
      <path
        d="M5 2.5h9l5 5v14H5z"
        fill="none"
        stroke="currentColor"
        strokeLinejoin="round"
        strokeWidth="1.5"
      />
      <path d="M14 2.5v5h5" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <path d="M8 13h8M8 16.5h5" stroke="currentColor" strokeLinecap="round" strokeWidth="1.5" />
    </svg>
  )
}

/** Family: two figures of different height on one baseline. */
function FamilyA({ size = 24, className }: MarkProps) {
  return (
    <svg className={className} height={size} viewBox="0 0 24 24" width={size} {...hidden}>
      <circle cx="8" cy="6.5" fill="none" r="3" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="17" cy="11" fill="none" r="2.4" stroke="currentColor" strokeWidth="1.5" />
      <path
        d="M2.8 20.5c0-3.4 2.3-5.6 5.2-5.6s5.2 2.2 5.2 5.6"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeWidth="1.5"
      />
      <path
        d="M13.6 20.5c0-2.6 1.6-4.2 3.4-4.2s3.4 1.6 3.4 4.2"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeWidth="1.5"
      />
    </svg>
  )
}

/** Staff: a queue of rows with the current one marked. */
function StaffA({ size = 24, className }: MarkProps) {
  return (
    <svg className={className} height={size} viewBox="0 0 24 24" width={size} {...hidden}>
      <rect
        fill="none"
        height="17"
        rx="1.5"
        stroke="currentColor"
        strokeWidth="1.5"
        width="19"
        x="2.5"
        y="3.5"
      />
      <path d="M2.5 9h19" stroke="currentColor" strokeWidth="1.5" />
      <path d="M2.5 14.5h19" stroke="currentColor" strokeWidth="1.1" />
      <path
        d="M6 17.6l2 2 4-4.2"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.6"
      />
    </svg>
  )
}

function StudentB({ size = 24, className }: MarkProps) {
  return (
    <svg className={className} height={size} viewBox="0 0 24 24" width={size} {...hidden}>
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
        d="M7.5 12h9M7.5 16h5.5"
        stroke="currentColor"
        strokeLinecap="round"
        strokeWidth="1.75"
      />
      <path d="M7.5 7.5h9" stroke="currentColor" strokeLinecap="round" strokeWidth="1.75" />
    </svg>
  )
}

function FamilyB({ size = 24, className }: MarkProps) {
  return (
    <svg className={className} height={size} viewBox="0 0 24 24" width={size} {...hidden}>
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

function StaffB({ size = 24, className }: MarkProps) {
  return (
    <svg className={className} height={size} viewBox="0 0 24 24" width={size} {...hidden}>
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
        d="M12 16.5l2 2 3.6-4"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.75"
      />
    </svg>
  )
}

function StudentC({ size = 24, className }: MarkProps) {
  return (
    <svg className={className} height={size} viewBox="0 0 24 24" width={size} {...hidden}>
      <path d="M4 3h11l5 5v13H4z" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <path d="M15 3v5h5" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <path d="M7.5 12.5h9M7.5 15.2h9M7.5 17.9h5" stroke="currentColor" strokeWidth="1.3" />
    </svg>
  )
}

function FamilyC({ size = 24, className }: MarkProps) {
  return (
    <svg className={className} height={size} viewBox="0 0 24 24" width={size} {...hidden}>
      <rect fill="none" height="6" stroke="currentColor" strokeWidth="1.8" width="6" x="3" y="4" />
      <rect
        fill="none"
        height="4.6"
        stroke="currentColor"
        strokeWidth="1.8"
        width="4.6"
        x="14.4"
        y="9"
      />
      <path d="M3 21v-5.6h6V21" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <path d="M14.4 21v-4.2H19V21" fill="none" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  )
}

function StaffC({ size = 24, className }: MarkProps) {
  return (
    <svg className={className} height={size} viewBox="0 0 24 24" width={size} {...hidden}>
      <rect
        fill="none"
        height="16"
        stroke="currentColor"
        strokeWidth="1.8"
        width="18"
        x="3"
        y="4"
      />
      <path d="M3 9h18M3 14h18M9 4v16" stroke="currentColor" strokeWidth="1.3" />
      <path
        d="M12.6 16.6l2 2 3.8-4.2"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
    </svg>
  )
}

export interface MarkSet {
  Sign: (props: MarkProps) => React.JSX.Element
  Wordmark: (props: MarkProps) => React.JSX.Element
  Student: (props: MarkProps) => React.JSX.Element
  Family: (props: MarkProps) => React.JSX.Element
  Staff: (props: MarkProps) => React.JSX.Element
}

export const markSets: Record<DirectionId, MarkSet> = {
  a: { Sign: SignA, Wordmark: WordmarkA, Student: StudentA, Family: FamilyA, Staff: StaffA },
  b: { Sign: SignB, Wordmark: WordmarkB, Student: StudentB, Family: FamilyB, Staff: StaffB },
  c: { Sign: SignC, Wordmark: WordmarkC, Student: StudentC, Family: FamilyC, Staff: StaffC },
}
