import { describe, it, expect } from 'vitest'
import { teacherWorkCommandSchema, teacherWorkReportSchema } from './teacher-work'

describe('teacher accounting contracts', () => {
  it('requires finite nonnegative absolute hours and an explanation', () => {
    const body = {
      action: 'override',
      courseId: 'c-1',
      idempotencyKey: 'test',
      expectedVersion: 0,
      cellKey: 'zoom:1:2026-09-14',
      hours: 0,
      comment: 'Фактическое отсутствие',
      sourceFingerprint: 'abc',
    }
    expect(teacherWorkCommandSchema.parse(body).action).toBe('override')
    expect(teacherWorkCommandSchema.safeParse({ ...body, comment: ' ' }).success).toBe(false)
    expect(teacherWorkCommandSchema.safeParse({ ...body, hours: NaN }).success).toBe(false)
    expect(teacherWorkCommandSchema.safeParse({ ...body, hours: -1 }).success).toBe(false)
    expect(teacherWorkCommandSchema.safeParse({ ...body, hours: null }).success).toBe(true)
  })
  it('rejects incomplete report matrices', () => {
    const body = {
      run: null,
      operation: null,
      lessons: [],
      columns: [],
      rows: [
        {
          teacherId: 'u-1',
          id: 1,
          surname: 'А',
          name: 'Б',
          middlename: '',
          counts: { school: 0, zoom: 0, written: 0 },
          totals: { school: 0, zoom: null, written: 0 },
          totalHours: null,
          cells: [
            { columnKey: 'x', keys: [], hours: null, sources: [], stale: false, anomalies: [] },
          ],
        },
      ],
      tsv: '',
    }
    expect(teacherWorkReportSchema.safeParse(body).success).toBe(false)
    expect(teacherWorkReportSchema.parse({ ...body, rows: [] }).rows).toEqual([])
  })
})
