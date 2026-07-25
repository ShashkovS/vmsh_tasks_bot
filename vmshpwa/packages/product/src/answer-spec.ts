/*
 * Test-answer specification. The application maps a task's `ANS_TYPE`
 * (helpers/consts.py) + course data into an AnswerSpec; the input renders the
 * matching affordance and always shows a plain-Russian format hint with an
 * example — the student reads what to enter, never a bare code. Correctness is
 * decided by the server; the client only helps with format.
 */
export type AnswerType =
  | 'digit'
  | 'natural'
  | 'integer'
  | 'ratio'
  | 'float'
  | 'float-eps'
  | 'fraction'
  | 'mixed-fraction'
  | 'polynomial'
  | 'int-2'
  | 'int-3'
  | 'int-4'
  | 'int-seq'
  | 'int-set'
  | 'frac-seq'
  | 'multiset'
  | 'time'
  | 'date'
  | 'weekday'
  | 'symb-expression'
  | 'symb-equiv'
  | 'select-one'
  | 'string'

/** Input archetype — many answer types share one affordance. */
export type AnswerInputKind = 'scalar' | 'tuple' | 'list' | 'choice'

export interface AnswerOption {
  value: string
  label: string
}

export interface AnswerSpec {
  type: AnswerType
  /** Plain-Russian format description; falls back to a per-type default. */
  hint?: string
  /** Example answer, shown next to the hint and as placeholder. */
  example?: string
  /** Fixed arity for tuples (int-2/3/4); derived from the type if omitted. */
  arity?: number
  /** Options for `select-one`. */
  options?: AnswerOption[]
  /** Optional per-problem regex from `ans_validation`, without fullmatch anchors. */
  validationPattern?: string
  /** Existing per-problem validation message shown when the format is invalid. */
  validationError?: string
}

const tupleArity: Partial<Record<AnswerType, number>> = {
  'int-2': 2,
  'int-3': 3,
  'int-4': 4,
}

const listTypes = new Set<AnswerType>(['int-seq', 'int-set', 'frac-seq', 'multiset'])

export function answerInputKind(type: AnswerType): AnswerInputKind {
  if (type === 'select-one') return 'choice'
  if (tupleArity[type] !== undefined) return 'tuple'
  if (listTypes.has(type)) return 'list'
  return 'scalar'
}

export function resolveArity(spec: AnswerSpec): number {
  return spec.arity ?? tupleArity[spec.type] ?? 2
}

/*
 * On-screen keyboard hint. Only digit/natural get the pure numeric pad; signed,
 * fractional and expression forms need punctuation, so they keep the full
 * keyboard.
 */
export function answerInputMode(type: AnswerType): 'numeric' | 'decimal' | 'text' {
  if (type === 'digit' || type === 'natural') return 'numeric'
  if (type === 'float' || type === 'float-eps') return 'decimal'
  return 'text'
}

const defaults: Record<AnswerType, { hint: string; example: string }> = {
  digit: { hint: 'Введите одну цифру', example: '7' },
  natural: { hint: 'Введите натуральное число', example: '179' },
  integer: { hint: 'Введите целое число', example: '-179' },
  ratio: { hint: 'Введите отношение', example: '5/3' },
  float: { hint: 'Введите десятичную дробь', example: '3.14' },
  'float-eps': { hint: 'Введите десятичную дробь (можно приближённо)', example: '3.14' },
  fraction: { hint: 'Введите обыкновенную или десятичную дробь', example: '7/3' },
  'mixed-fraction': { hint: 'Введите смешанную дробь', example: '1 2/3' },
  polynomial: { hint: 'Введите выражение от n', example: '2n^2 + n(n+1)/2' },
  'int-2': { hint: 'Введите два целых числа', example: '1, 7' },
  'int-3': { hint: 'Введите три целых числа', example: '1, 7, 9' },
  'int-4': { hint: 'Введите четыре целых числа', example: '0, 1, 7, 9' },
  'int-seq': {
    hint: 'Целые числа через запятую — порядок важен',
    example: '1, 7, 9',
  },
  'int-set': {
    hint: 'Целые числа через запятую — порядок и повторы не важны',
    example: '1, 7, 9',
  },
  'frac-seq': { hint: 'Дроби через запятую — порядок важен', example: '2/5, 3.75, -1' },
  multiset: {
    hint: 'Числа через запятую — повторы учитываются, порядок нет',
    example: '1, 1, 2, 2/5',
  },
  time: { hint: 'Введите время', example: '12:08' },
  date: { hint: 'Введите дату', example: '31.12' },
  weekday: { hint: 'Введите день недели', example: 'суббота' },
  'symb-expression': { hint: 'Введите символьное выражение', example: 'a + b^2' },
  'symb-equiv': { hint: 'Введите тождественно равное выражение', example: 'b*b + a' },
  'select-one': { hint: 'Выберите один вариант', example: '' },
  string: { hint: 'Введите ответ', example: '' },
}

export function defaultAnswerHint(type: AnswerType): { hint: string; example: string } {
  return defaults[type]
}

/** Split a comma/space separated list answer into trimmed, non-empty items. */
export function parseListAnswer(raw: string): string[] {
  return raw
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}
