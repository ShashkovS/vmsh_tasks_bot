import { describe, expect, it } from 'vitest'
import { liveCommandSchema, liveDirectorySchema } from './live-marking'
const mark = {
  kind: 'mark',
  context: { mode: 'zoom', contextId: 'session-1' },
  operationId: 'op-1',
  studentId: 'u-1',
  problemId: 'p-1',
  expectedVersion: 0,
  value: 'plus',
}
describe('live marking commands', () => {
  it('requires an explicit target state and conflict version, never a server toggle', () => {
    expect(liveCommandSchema.safeParse(mark).success).toBe(true)
    expect(liveCommandSchema.safeParse({ ...mark, value: 'toggle' }).success).toBe(false)
    expect(liveCommandSchema.safeParse({ ...mark, expectedVersion: true }).success).toBe(false)
    expect(liveCommandSchema.safeParse({ ...mark, teacherId: 'spoof' }).success).toBe(false)
  })

  it('keeps surname separate in the student directory', () => {
    const directory = liveDirectorySchema.parse({
      schemaVersion: 1,
      requestId: 'request-1',
      students: [
        {
          studentId: 'u-1',
          displayName: 'Де ла Крус Анна',
          surname: 'Де ла Крус',
          middleName: 'Сергеевна',
          grade: 7,
          groupId: 'g-1',
          groupName: 'Начинающие',
          attendanceMode: 'online',
          enrollmentVersion: 1,
          rooms: [],
        },
      ],
    })

    expect(directory.students[0]?.surname).toBe('Де ла Крус')
  })
})
