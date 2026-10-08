import { describe, expect, it } from 'vitest'
import { whiteboardCatalogSchema, whiteboardExportSchema } from './whiteboard-export'

// Production regression: the introductory lesson 0 must not invalidate the
// entire catalog. See docs/whiteboard-export.md.
const sheet = {
  groupLessonId: 'gl-1',
  courseId: 'c-1',
  courseCode: 'vmsh',
  courseName: 'ВМШ 2026-2027',
  lessonNumber: 0,
  lessonTitle: 'Знакомство',
  groupId: 'g-5',
  groupCode: 'н',
  groupName: 'Начинающие',
  publicationId: 'lp-5',
  revisionId: 'cr-7',
}

describe('whiteboard introductory lessons', () => {
  it('accepts a mixed catalog of lessons 1 and 0 across three levels', () => {
    const sheets = [1, 0].flatMap((lessonNumber) =>
      ['н', 'п', 'э'].map((groupCode) => ({
        ...sheet,
        lessonNumber,
        groupCode,
        lessonTitle: lessonNumber === 0 ? 'Знакомство' : null,
      })),
    )
    expect(whiteboardCatalogSchema.parse({ sheets }).sheets).toEqual(sheets)
  })

  it('accepts the selected introductory worksheet', () => {
    const payload = {
      sheet,
      document: {
        contractVersion: 1,
        revisionId: 'cr-7',
        sourceSha256: 'a'.repeat(64),
        materialKind: 'condition',
        title: 'Знакомство',
        introduction: [],
        problems: [
          {
            ordinal: 1,
            sourceItem: null,
            title: null,
            blocks: [{ type: 'paragraph', children: [{ type: 'text', value: 'Условие.' }] }],
          },
        ],
      },
      statistics: null,
      statisticsError: false,
    }
    expect(whiteboardExportSchema.parse(payload).sheet.lessonNumber).toBe(0)
  })

  it.each([-1, 0.5])('still rejects invalid lesson number %s', (lessonNumber) => {
    expect(
      whiteboardCatalogSchema.safeParse({ sheets: [{ ...sheet, lessonNumber }] }).success,
    ).toBe(false)
  })
})
