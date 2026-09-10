import { describe, expect, it } from 'vitest'
import { liveCommandSchema } from './live-marking'
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
})
