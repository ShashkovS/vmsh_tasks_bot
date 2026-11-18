import { describe, expect, it } from 'vitest'

import { ApiResponseError, type ContentUploadTarget } from '@vmsh/contracts'

import {
  bulkContentRecoveryHref,
  bulkContentRevisionId,
  bulkContentUploadErrorMessage,
  createBulkContentUploadRows,
  validateBulkContentUploadRows,
} from './bulk-content-upload-model'

const targets: ContentUploadTarget[] = [
  {
    groupLessonId: 'group-lesson-41-n',
    groupId: 'group-beginner',
    groupName: 'Начинающие',
    groupShortCode: 'н',
    colorKey: 'level-1',
    status: 'active',
  },
  {
    groupLessonId: 'group-lesson-41-archived',
    groupId: 'group-archived',
    groupName: 'Архивная',
    groupShortCode: 'а',
    colorKey: null,
    status: 'archived',
  },
]

describe('Staff bulk content upload validation', () => {
  it('defaults every selected LaTeX file to a condition and requires an active group', () => {
    const [row] = createBulkContentUploadRows([new File(['tex'], 'condition.tex')])

    expect(row?.kind).toBe('condition')
    expect(validateBulkContentUploadRows([row!], targets)).toContain('Выберите действующую группу')
    expect(
      validateBulkContentUploadRows(
        [
          {
            ...row!,
            groupLessonId: targets[1]!.groupLessonId,
            kind: 'condition',
          },
        ],
        targets,
      ),
    ).toContain('Выберите действующую группу')
  })

  it('recognises the shared hints-and-solutions source by its established filename', () => {
    const [row] = createBulkContentUploadRows([new File(['tex'], 'usl-20-n-sol.tex')])

    expect(row?.kind).toBe('hint_solution')
  })

  it('rejects duplicate group/material slots instead of silently overwriting a revision', () => {
    const rows = createBulkContentUploadRows([
      new File(['first'], 'first.tex'),
      new File(['second'], 'second.tex'),
    ]).map((row) => ({
      ...row,
      groupLessonId: targets[0]!.groupLessonId,
      kind: 'condition' as const,
    }))

    expect(validateBulkContentUploadRows(rows, targets)).toBe(
      'Одна группа и вид материала выбраны для нескольких файлов.',
    )
  })

  it('treats one combined solution file as occupying both hint and solution slots', () => {
    const [combined] = createBulkContentUploadRows([new File(['combined'], 'usl-20-n-sol.tex')])
    const [separate] = createBulkContentUploadRows([new File(['hint'], 'hint.tex')])

    expect(
      validateBulkContentUploadRows(
        [
          { ...combined!, groupLessonId: targets[0]!.groupLessonId },
          { ...separate!, groupLessonId: targets[0]!.groupLessonId, kind: 'hint' },
        ],
        targets,
      ),
    ).toBe('Одна группа и вид материала выбраны для нескольких файлов.')
  })

  it('checks file type and the same 512 KiB source boundary as aiohttp', () => {
    const invalidExtension = {
      ...createBulkContentUploadRows([new File(['tex'], 'condition.txt')])[0]!,
      groupLessonId: targets[0]!.groupLessonId,
      kind: 'condition' as const,
    }
    const oversized = {
      ...createBulkContentUploadRows([
        new File([new Uint8Array(512 * 1024 + 1)], 'condition.tex'),
      ])[0]!,
      groupLessonId: targets[0]!.groupLessonId,
      kind: 'condition' as const,
    }

    expect(validateBulkContentUploadRows([invalidExtension], targets)).toContain('.tex')
    expect(validateBulkContentUploadRows([oversized], targets)).toContain('больше 512 КБ')
  })

  it('accepts a complete explicit mapping', () => {
    const row = {
      ...createBulkContentUploadRows([new File(['tex'], 'condition.tex')])[0]!,
      groupLessonId: targets[0]!.groupLessonId,
      kind: 'condition' as const,
    }

    expect(validateBulkContentUploadRows([row], targets)).toBeUndefined()
  })

  it('links an attention row back to the exact lesson and material card', () => {
    const row = {
      ...createBulkContentUploadRows([new File(['tex'], 'condition.tex')])[0]!,
      groupLessonId: targets[0]!.groupLessonId,
      revisionId: 'content-revision.condition',
      phase: 'attention' as const,
    }

    expect(bulkContentRecoveryHref(row)).toBe('/staff/lessons/group-lesson-41-n#material-condition')
  })

  it('links a saved attention row even when upload failed before the success response', () => {
    const row = {
      ...createBulkContentUploadRows([new File(['tex'], 'condition.tex')])[0]!,
      groupLessonId: targets[0]!.groupLessonId,
      revisionId: undefined,
      phase: 'attention' as const,
    }

    expect(bulkContentRecoveryHref(row)).toBe('/staff/lessons/group-lesson-41-n#material-condition')
  })

  it('links a combined-material failure to the lesson without inventing a fake anchor', () => {
    const row = {
      ...createBulkContentUploadRows([new File(['tex'], 'usl-20-n-sol.tex')])[0]!,
      groupLessonId: targets[0]!.groupLessonId,
      revisionId: 'content-revision.solution',
      phase: 'attention' as const,
    }

    expect(bulkContentRecoveryHref(row)).toBe('/staff/lessons/group-lesson-41-n')
  })

  it('explains a failed TikZ conversion and keeps the persisted revision id', () => {
    const error = new ApiResponseError(422, {
      error: {
        code: 'asset_conversion_failed',
        message: 'Рисунок не прошёл безопасную обработку',
        requestId: 'request-1',
        details: {
          reason: 'asset.converter_failed',
          detail: 'converter exited with code 1',
          logicalAsset: 'tikz-deadbeef',
          revisionId: 'content-revision.saved',
        },
      },
    })

    expect(bulkContentRevisionId(error)).toBe('content-revision.saved')
    expect(bulkContentUploadErrorMessage(error)).toContain('LaTeX-компилятор')
    expect(bulkContentUploadErrorMessage(error)).toContain('tikz-deadbeef')
    expect(bulkContentUploadErrorMessage(error)).toContain('converter exited with code 1')
  })
})
