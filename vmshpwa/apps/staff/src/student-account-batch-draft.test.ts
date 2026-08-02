import { describe, expect, it } from 'vitest'

import {
  readStudentAccountBatchDraft,
  studentAccountBatchDraftKey,
  writeStudentAccountBatchDraft,
} from './student-account-batch-draft'

class MemoryStorage {
  readonly values = new Map<string, string>()

  getItem(key: string) {
    return this.values.get(key) ?? null
  }

  setItem(key: string, value: string) {
    this.values.set(key, value)
  }
}

describe('student account batch draft', () => {
  it('keeps a de-duplicated account-scoped selection across reloads', () => {
    const storage = new MemoryStorage()
    const key = studentAccountBatchDraftKey('vmsh:staff:agent', 'staff-one')

    expect(
      writeStudentAccountBatchDraft(storage, key, ['student-b', 'student-a', 'student-b']),
    ).toBe(true)
    expect(readStudentAccountBatchDraft(storage, key)).toEqual({
      schemaVersion: 1,
      studentIds: ['student-b', 'student-a'],
    })
    expect(key).toBe('vmsh:staff:agent:draft:student-account-batch:staff-one')
  })

  it('falls back safely when the stored selection is invalid', () => {
    const storage = new MemoryStorage()
    storage.setItem('draft', '{"schemaVersion":2,"studentIds":["student-one"]}')

    expect(readStudentAccountBatchDraft(storage, 'draft')).toEqual({
      schemaVersion: 1,
      studentIds: [],
    })
  })
})
