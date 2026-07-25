import type { AnswerSpec, AnswerType } from './answer-spec'

/*
 * Client-side mirror of helpers/checkers.py: strip first, then fullmatch the
 * ANS_REGEX for the chosen legacy type. The server remains authoritative; this
 * exists only to show a format error before a round trip.
 */
const fraction = '[+-]?(?=[0-9]|\\.[0-9])[0-9]*(?:/[0-9]+|(?:\\.[0-9]*)?(?:[eE][-+]?[0-9]+)?|)'

const formatPatterns: Partial<Record<AnswerType, RegExp>> = {
  digit: /^[0-9]$/,
  natural: /^[0-9]+$/,
  integer: /^[-+]?[0-9]+$/,
  ratio: /^[-+]?[0-9]+(?:\/[0-9]+)?$/,
  float: new RegExp(`^(?:${fraction})$`),
  'float-eps': new RegExp(`^(?:${fraction})$`),
  fraction: /^[-+]?(?=[0-9]+|\.[0-9]+)[0-9]*(?:(?:\/[0-9]+)?|(?:\.[0-9]*)?(?:[eE][-+]?[0-9]+)?)$/,
  'mixed-fraction': /^([+-]?) ?(?:(\d+)\s+(\d+\s*\/\s*\d+)|(\d+\s*\/\s*\d+|\d*[.,]\d+|\d+))$/,
  'int-seq': /^[^0-9+-]*[-+]?\d+(?:[^0-9+-]+[-+]?\d+)*[^0-9+-]*$/,
  'int-set': /^[^0-9+-]*[-+]?\d+(?:[^0-9+-]+[-+]?\d+)*[^0-9+-]*$/,
  'int-2': /^[^0-9+-]*[-+]?\d+(?:[^0-9+-]+[-+]?\d+){1}[^0-9+-]*$/,
  'int-3': /^[^0-9+-]*[-+]?\d+(?:[^0-9+-]+[-+]?\d+){2}[^0-9+-]*$/,
  'int-4': /^[^0-9+-]*[-+]?\d+(?:[^0-9+-]+[-+]?\d+){3}[^0-9+-]*$/,
  polynomial: /^[ \d+\-*/()nkijmxyzt^]+$/,
  time: /^\d{1,2}(?:\D{1,2}\d{1,2}){1,2}$/,
  date: /^\d{1,4}(?:\D{1,2}\d{1,4}){1,2}$/,
  weekday: /^(?:п.?н|вт|ср|ч.?т|п.?т|с.?б|в.?с).*$/i,
  'frac-seq': new RegExp(`^(?:[^0-9eE.+/-]*(?:${fraction})[^0-9eE.+/-]*)+$`),
  multiset: new RegExp(`^(?:[^0-9eE.+/-]*(?:${fraction})[^0-9eE.+/-]*)+$`),
  'symb-expression': /^.*$/,
  'symb-equiv': /^.*$/,
}

export function validateAnswerFormat(spec: AnswerSpec, raw: string): boolean {
  const value = raw.trim()
  const override = spec.validationPattern
  if (override) {
    try {
      return new RegExp(`^(?:${override})$`).test(value)
    } catch {
      return false
    }
  }
  const pattern = formatPatterns[spec.type]
  return pattern ? pattern.test(value) : true
}

/** Values as the current legacy parser will account for them, for list preview. */
export function parseLegacyAnswerItems(type: AnswerType, raw: string): string[] {
  const value = raw.trim()
  if (type === 'int-seq' || type === 'int-set' || type.startsWith('int-')) {
    return value.match(/[-+]?\d+/g) ?? []
  }
  if (type === 'frac-seq' || type === 'multiset') {
    return value.match(new RegExp(fraction, 'g')) ?? []
  }
  return value ? [value] : []
}
