import { describe, expect, it } from 'vitest'

import { answerTypeFromLegacyId } from './answer-spec'
import { parseLegacyAnswerItems, validateAnswerFormat } from './answer-validation'

describe('legacy answer format mirror', () => {
  it('maps every historical numeric answer type and rejects unknown values', () => {
    expect(
      [1, 2, 3, 4, 5, 6, 19, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 20, 21, 98, 99].map(
        answerTypeFromLegacyId,
      ),
    ).toHaveLength(23)
    expect(answerTypeFromLegacyId(98)).toBe('select-one')
    expect(() => answerTypeFromLegacyId(22)).toThrow(RangeError)
  })

  it.each([
    ['digit', '7', true],
    ['digit', '17', false],
    ['natural', ' 179 ', true],
    ['integer', '-179', true],
    ['ratio', '5/3', true],
    ['mixed-fraction', '1 2/3', true],
    ['int-3', '1, 7, 9', true],
    ['int-3', '1, 7жф, 9, 10', false],
    ['time', '3:15:24', true],
    ['date', '2025-02-16', true],
    ['weekday', 'Суббота', true],
    ['polynomial', '2n^2 + n(n+1)/2', true],
  ] as const)('%s / %s', (type, value, expected) => {
    expect(validateAnswerFormat({ type }, value)).toBe(expected)
  })

  it('applies per-problem ans_validation as a full match', () => {
    const spec = { type: 'string' as const, validationPattern: '[А-Я][0-9]+' }
    expect(validateAnswerFormat(spec, 'Ж1000')).toBe(true)
    expect(validateAnswerFormat(spec, 'ответ Ж1000')).toBe(false)
  })

  it('previews the values parsed from a valid integer sequence', () => {
    expect(parseLegacyAnswerItems('int-seq', '1; -7, +9')).toEqual(['1', '-7', '+9'])
  })
})
