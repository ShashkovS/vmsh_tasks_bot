import { describe, expect, it } from 'vitest'

import {
  clearStudentAccountDraft,
  readStudentAccountDraft,
  studentAccountDraftKey,
  writeStudentAccountDraft,
} from './student-account-draft'

function memoryStorage() {
  const values = new Map<string, string>()
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
    removeItem: (key: string) => values.delete(key),
  }
}

describe('Student account draft', () => {
  it('keeps only the non-secret login and isolates students', () => {
    const storage = memoryStorage()
    const first = studentAccountDraftKey('agent', 'admin-one', 'student-one')
    const second = studentAccountDraftKey('agent', 'admin-one', 'student-two')

    expect(
      writeStudentAccountDraft(storage, first, { schemaVersion: 1, username: 'student-17' }),
    ).toBe(true)
    expect(readStudentAccountDraft(storage, first).username).toBe('student-17')
    expect(readStudentAccountDraft(storage, second).username).toBe('')

    clearStudentAccountDraft(storage, first)
    expect(readStudentAccountDraft(storage, first).username).toBe('')
  })

  it('fails closed on extra persisted fields', () => {
    const storage = memoryStorage()
    storage.setItem('draft', JSON.stringify({ schemaVersion: 1, username: 'x', token: 'secret' }))
    expect(readStudentAccountDraft(storage, 'draft')).toEqual({ schemaVersion: 1, username: '' })
  })
})
