import { expect, it } from 'vitest'
import { statisticsSummarySchema, statisticsPlusTableSchema } from './statistics-reports'
const envelope = {
  schemaVersion: 1,
  courses: [],
  selectedCourseId: null,
  selectedGroupId: null,
  requestId: 'test',
}
it('rejects inconsistent workload and matrix totals', () => {
  expect(
    statisticsSummarySchema.safeParse({
      ...envelope,
      lessons: [
        {
          lessonNumber: 0,
          students: 1,
          allPlus: 1,
          botPlus: 1,
          writtenPlus: 0,
          writtenWrittenPlus: 0,
          writtenOralPlus: 0,
          zoomPlus: 0,
          schoolPlus: 0,
          writtenChecked: 2,
          writtenPending: 1,
          writtenTotal: 2,
          writtenStudents: 0,
          zoomStudents: 0,
          schoolStudents: 0,
        },
      ],
    }).success,
  ).toBe(false)
  expect(
    statisticsPlusTableSchema.safeParse({
      ...envelope,
      lessonNumbers: [0],
      lessonNumber: 0,
      problems: [],
      rows: [{ studentId: 'u-1', name: 'Тест', total: 1, cells: [] }],
    }).success,
  ).toBe(false)
})
