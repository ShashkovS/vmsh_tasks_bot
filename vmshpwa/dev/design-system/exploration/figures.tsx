/**
 * Deterministic repo-native SVG stand-ins for the real assets of listok 21н:
 * the chessboard of problem 21н.6, the symmetry figure of 21н.7, photographed
 * notebook pages and Telegram album thumbnails. No bitmaps, no network.
 */

const grid = Array.from({ length: 9 }, (_, index) => index)
/** Problem 21н.6 a): eight rooks that do not attack each other. */
const rooks = [0, 1, 2, 3, 4, 5, 6, 7].map((file, index) => ({ file, rank: (index * 5) % 8 }))

export function ChessRooksFigure({ size = 168 }: { size?: number }) {
  const cell = 18
  return (
    <svg
      height={size}
      role="img"
      viewBox="0 0 152 152"
      width={size}
      aria-label="Шахматная доска 8 на 8, на которой расставлены восемь ладей: по одной в каждой горизонтали и каждой вертикали."
    >
      <rect
        fill="none"
        height="144"
        stroke="currentColor"
        strokeWidth="1.6"
        width="144"
        x="4"
        y="4"
      />
      {grid.map((index) => (
        <g key={index} opacity="0.45" stroke="currentColor" strokeWidth="0.8">
          <path d={`M${4 + index * cell} 4V148`} />
          <path d={`M4 ${4 + index * cell}H148`} />
        </g>
      ))}
      {rooks.map((rook) => {
        const x = 4 + rook.file * cell + cell / 2
        const y = 4 + rook.rank * cell + cell / 2
        return (
          <g key={`${rook.file}-${rook.rank}`} fill="currentColor">
            <path
              d={`M${x - 5} ${y + 5}h10l-1.4-7h1.9v-3.4h-2.6v1.7h-2v-1.7h-2.2v1.7h-2v-1.7H${x - 5.4}v3.4h1.9z`}
            />
          </g>
        )
      })}
    </svg>
  )
}

export function SymmetryFigure({ size = 168 }: { size?: number }) {
  return (
    <svg
      height={size}
      role="img"
      viewBox="0 0 152 152"
      width={size}
      aria-label="Половина бабочки на клетчатой бумаге: тело расположено вдоль вертикальной оси, левое крыло и левый усик нарисованы, правые нужно достроить симметрично."
    >
      <g opacity="0.35" stroke="currentColor" strokeWidth="0.8">
        {grid.map((index) => (
          <path d={`M${4 + index * 18} 4V148`} key={`v${index}`} />
        ))}
        {grid.map((index) => (
          <path d={`M4 ${4 + index * 18}H148`} key={`h${index}`} />
        ))}
      </g>
      <path d="M76 14v124" stroke="currentColor" strokeDasharray="6 5" strokeWidth="1.4" />
      {/* upper-left wing */}
      <path
        d="M72 44C58 24 30 22 22 40c-7 16 8 30 26 30h24z"
        fill="currentColor"
        fillOpacity="0.12"
        stroke="currentColor"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
      {/* lower-left wing */}
      <path
        d="M72 76H50c-14 0-24 12-20 26 4 13 24 16 34 2z"
        fill="currentColor"
        fillOpacity="0.12"
        stroke="currentColor"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
      {/* left antenna */}
      <path
        d="M73 40c-4-10-10-16-19-19"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeWidth="1.8"
      />
      <circle cx="53" cy="20" fill="currentColor" r="2.6" />
      {/* body on the axis */}
      <path
        d="M72 38h8v76h-8z"
        fill="currentColor"
        fillOpacity="0.22"
        stroke="currentColor"
        strokeWidth="1.6"
      />
    </svg>
  )
}

/** A photographed notebook page: the immutable evidence a student uploads. */
export function NotebookPhoto({ variant = 1, width = 104 }: { variant?: 1 | 2; width?: number }) {
  const lines = variant === 1 ? [22, 34, 46, 58, 70, 82, 94] : [26, 38, 50, 62, 74, 86]
  const widths = variant === 1 ? [70, 84, 52, 78, 88, 44, 66] : [80, 58, 86, 72, 40, 76]
  return (
    <svg
      height={(width * 132) / 104}
      role="img"
      viewBox="0 0 104 132"
      width={width}
      aria-label={`Фотография страницы с рукописным решением, лист ${variant}`}
    >
      <rect fill="currentColor" fillOpacity="0.04" height="132" width="104" />
      <g opacity="0.25" stroke="currentColor" strokeWidth="0.7">
        {lines.map((y) => (
          <path d={`M10 ${y}H94`} key={y} />
        ))}
        <path d="M18 6V126" />
      </g>
      <g opacity="0.8" stroke="currentColor" strokeLinecap="round" strokeWidth="1.7">
        {lines.map((y, index) => (
          <path
            d={`M22 ${y - 3}h${widths[index]}`}
            key={y}
            opacity={index % 3 === 0 ? 0.55 : 0.8}
          />
        ))}
      </g>
      <path
        d="M24 104h20M24 112h34"
        opacity="0.55"
        stroke="currentColor"
        strokeLinecap="round"
        strokeWidth="1.7"
      />
    </svg>
  )
}

/** Abstract album thumbnails for a Telegram post: board, room, sheet, plot. */
export function AlbumThumb({ variant }: { variant: 1 | 2 | 3 | 4 }) {
  return (
    <svg role="img" viewBox="0 0 64 64" aria-label={`Фотография ${variant} из альбома занятия`}>
      <rect fill="currentColor" fillOpacity="0.07" height="64" width="64" />
      {variant === 1 ? (
        <g opacity="0.65" stroke="currentColor" strokeLinecap="round" strokeWidth="2">
          <rect fill="none" height="30" width="44" x="10" y="12" />
          <path d="M17 24h20M17 32h28M17 40h14" />
        </g>
      ) : null}
      {variant === 2 ? (
        <g opacity="0.65" stroke="currentColor" strokeWidth="2">
          <circle cx="22" cy="24" fill="none" r="7" />
          <circle cx="42" cy="27" fill="none" r="5.5" />
          <path d="M10 52c0-8 5.5-13 12-13s12 5 12 13" fill="none" />
          <path d="M34 52c0-6 4-10 8.5-10S51 46 51 52" fill="none" />
        </g>
      ) : null}
      {variant === 3 ? (
        <g opacity="0.65" stroke="currentColor" strokeWidth="2">
          <path d="M18 8h20l10 10v38H18z" fill="none" strokeLinejoin="round" />
          <path d="M38 8v10h10" fill="none" />
          <path d="M25 30h16M25 38h16M25 46h9" strokeLinecap="round" />
        </g>
      ) : null}
      {variant === 4 ? (
        <g opacity="0.65" stroke="currentColor" strokeWidth="2">
          <path d="M12 52V14M12 52h40" strokeLinecap="round" />
          <path
            d="M18 44l10-12 8 7 12-18"
            fill="none"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </g>
      ) : null}
    </svg>
  )
}
