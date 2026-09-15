import { describe, expect, it } from 'vitest'

import inputFixture from '@vmsh/contracts/fixtures/submissions/input.v1.json'
import { testAnswerInputResponseSchema } from '@vmsh/contracts'

import { testAnswerSpec } from './student-test-answer-view'

describe('Student production test-answer view model', () => {
  it('uses visible SELECT_ONE labels as the exact submitted values', () => {
    const input = testAnswerInputResponseSchema.parse(inputFixture.response)

    expect(testAnswerSpec(input)).toEqual({
      type: 'select-one',
      validationError: 'Выберите, какой вариант подходит',
      options: [
        { value: 'Чётное', label: 'Чётное' },
        { value: 'Нечётное', label: 'Нечётное' },
        { value: 'Не определяется', label: 'Не определяется' },
      ],
    })
  })

  it('keeps a custom non-select fullmatch pattern and format message', () => {
    const input = testAnswerInputResponseSchema.parse({
      ...inputFixture.response,
      answerType: 99,
      validationPattern: '[А-Я][0-9]+',
      validationError: 'Введите букву и число',
      options: [],
    })

    expect(testAnswerSpec(input)).toEqual({
      type: 'string',
      validationPattern: '[А-Я][0-9]+',
      validationError: 'Введите букву и число',
    })
  })
})
