import { describe, expect, it } from 'vitest'

import {
  clearEnrollmentDraft,
  enrollmentDraftKey,
  readEnrollmentDraft,
  writeEnrollmentDraft,
} from './student-enrollment-draft'

const fallback = {
  schemaVersion: 1 as const,
  activeGroupId: 'group-beginner',
  allowedGroupIds: ['group-beginner'],
  attendanceMode: 'online' as const,
  status: 'active' as const,
}

describe('Student enrollment draft', () => {
  it('restores a validated unsaved edit under the exact server version', () => {
    const values = new Map<string, string>()
    const storage = {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
      removeItem: (key: string) => values.delete(key),
    }
    const key = enrollmentDraftKey('vmsh-179:v1:staff:e2e', 'admin', 'enrollment', 3)
    const changed = { ...fallback, attendanceMode: 'in_person' as const }

    expect(writeEnrollmentDraft(storage, key, changed)).toBe(true)
    expect(readEnrollmentDraft(storage, key, fallback)).toEqual(changed)
    clearEnrollmentDraft(storage, key)
    expect(readEnrollmentDraft(storage, key, fallback)).toEqual(fallback)
  })

  it('ignores malformed or internally inconsistent storage', () => {
    const storage = {
      getItem: () =>
        JSON.stringify({ ...fallback, activeGroupId: 'group-expert', allowedGroupIds: [] }),
    }
    expect(readEnrollmentDraft(storage, 'draft', fallback)).toEqual(fallback)
  })
})
