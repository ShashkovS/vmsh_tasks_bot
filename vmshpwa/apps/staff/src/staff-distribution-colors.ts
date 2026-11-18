/** Staff chart colours; docs/lesson-statistics.md#staff-violin-polish-2026-10-05. */
export function staffDistributionColorIndex(code: string, index = 0): 1 | 2 | 3 | 5 {
  switch (code.trim().toLowerCase()) {
    case 'н':
      return 2
    case 'п':
      return 3
    case 'э':
      return 5
    default:
      return index % 3 === 0 ? 1 : index % 3 === 1 ? 2 : 3
  }
}

export const staffDistributionPointColors = {
  1: 'fill-chart-1',
  2: 'fill-chart-2',
  3: 'fill-chart-3',
  5: 'fill-chart-5',
} as const
