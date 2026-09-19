import { describe, expect, it } from 'vitest'

import { problemImportPreviewResponseSchema, problemImportReceiptSchema } from './problem-import'

const preview = {
  schemaVersion: 1,
  course: { courseId: 'course-math', code: 'math', name: 'Математика' },
  source: { filename: 'tasks.xlsx', sha256: 'a'.repeat(64) },
  previewSha256: 'b'.repeat(64),
  summary: { rows: 1, create: 0, update: 0, unchanged: 0, invalid: 1 },
  rows: [
    {
      sheet: 'Задачи',
      row: 12,
      groupCode: 'н',
      groupId: null,
      lessonNumber: 41,
      problemNumber: 2,
      item: '',
      title: 'Орехи',
      problemText: '',
      problemType: 1,
      answerType: 2,
      answerValidation: null,
      validationError: 'Введите число',
      correctAnswer: '29',
      correctAnswerChecker: null,
      wrongAnswer: 'Нет',
      congratulation: 'Да',
      action: 'invalid',
      problemId: null,
      diagnostics: [
        {
          sheet: 'Задачи',
          row: 12,
          field: 'level',
          code: 'group_unknown',
          message: 'Такой группы нет.',
        },
      ],
    },
  ],
  synonymCandidates: [],
  requestId: 'request-one',
}

describe('problem import contract', () => {
  it('accepts an exact preview', () => {
    expect(problemImportPreviewResponseSchema.parse(preview).summary.invalid).toBe(1)
  })

  it('rejects inconsistent counts and strips additive row fields', () => {
    expect(() =>
      problemImportPreviewResponseSchema.parse({
        ...preview,
        summary: { ...preview.summary, invalid: 0 },
      }),
    ).toThrow()
    expect(
      problemImportPreviewResponseSchema.parse({
        ...preview,
        rows: [{ ...preview.rows[0], futureMetadata: 'ignored' }],
      }),
    ).toEqual(preview)
  })

  it('validates apply and rollback receipts', () => {
    const receipt = problemImportReceiptSchema.parse({
      schemaVersion: 1,
      importId: 'problem-import.one',
      state: 'applied',
      source: preview.source,
      previewSha256: preview.previewSha256,
      summary: { rows: 1, created: 0, updated: 0, unchanged: 0, skippedInvalid: 1 },
      appliedAt: '2026-07-30T10:00:00+00:00',
      rolledBackAt: null,
      version: 1,
      replayed: false,
      requestId: 'apply-one',
    })
    expect(receipt.state).toBe('applied')
    expect(() =>
      problemImportReceiptSchema.parse({
        ...receipt,
        summary: { ...receipt.summary, created: 1 },
      }),
    ).toThrow()
  })
})
