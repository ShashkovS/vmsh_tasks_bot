import type { VerdictTone, VerdictView } from './types'

interface CanonicalVerdict {
  symbol: string
  label: string
  weight: number
  tone: VerdictTone
}

/*
 * Canonical verdict values (helpers/consts.py VERDICT_DECODER + VERDICT_TO_NUM,
 * подписи приняты владельцем). A course exposes an ORDERED subset — binary,
 * ternary or the full olympiad scale — the UI never hardcodes which.
 */
export const canonicalVerdicts: Record<string, CanonicalVerdict> = {
  rejected: { symbol: '−', label: 'Отклонено', weight: 0, tone: 'negative' },
  'minus-dot': { symbol: '−.', label: 'Есть простая идея', weight: 0.05, tone: 'partial-low' },
  'minus-plus': { symbol: '∓', label: 'Есть идеи, не доведено', weight: 0.25, tone: 'partial-low' },
  half: { symbol: '+/2', label: 'Половина', weight: 0.5, tone: 'partial-mid' },
  'plus-minus': { symbol: '±', label: 'В целом верно', weight: 0.7, tone: 'partial-high' },
  'plus-dot': { symbol: '+.', label: 'Зачтено с недочётами', weight: 0.95, tone: 'positive' },
  plus: { symbol: '+', label: 'Зачтено', weight: 1, tone: 'positive' },
}

/** Builds an ordered registry (worst → best) from a course's allowed values. */
export function buildVerdictRegistry(values: readonly string[]): VerdictView[] {
  return values
    .filter((value) => value in canonicalVerdicts)
    .map((value) => ({ value, ...canonicalVerdicts[value]! }))
    .sort((a, b) => a.weight - b.weight)
}

export const fullVerdictScale = buildVerdictRegistry(Object.keys(canonicalVerdicts))
export const ternaryVerdictScale = buildVerdictRegistry(['rejected', 'half', 'plus'])
export const binaryVerdictScale = buildVerdictRegistry(['rejected', 'plus'])

export function findVerdict(registry: VerdictView[], value: string): VerdictView | undefined {
  return registry.find((verdict) => verdict.value === value)
}
