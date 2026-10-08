import { describe, expect, it } from 'vitest'

import {
  clearStaffAccessDraft,
  readStaffAccessDraft,
  staffAccessDraftKey,
  writeStaffAccessDraft,
} from './staff-access-draft'

function memoryStorage() {
  const values = new Map<string, string>()
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
    removeItem: (key: string) => values.delete(key),
  }
}

const scope = {
  courseId: 'course-math',
  courseCode: 'math',
  courseName: 'Математика',
  courseStatus: 'active' as const,
  groupId: 'group-beginner',
  groupCode: 'н',
  groupName: 'Начинающие',
  groupStatus: 'active' as const,
  version: 3,
}

describe('Staff access local draft', () => {
  it('is isolated by runtime, account, member and authoritative versions', () => {
    expect(staffAccessDraftKey('runtime-a', 'admin-a', 'teacher-a', [scope])).toBe(
      'runtime-a:draft:staff-access:admin-a:teacher-a:course-math:group-beginner:v3',
    )
    expect(staffAccessDraftKey('runtime-b', 'admin-a', 'teacher-a', [scope])).not.toBe(
      staffAccessDraftKey('runtime-a', 'admin-a', 'teacher-a', [scope]),
    )
    expect(staffAccessDraftKey('runtime-a', 'admin-a', 'teacher-a', [scope])).not.toBe(
      staffAccessDraftKey('runtime-a', 'admin-a', 'teacher-a', [{ ...scope, version: 4 }]),
    )
  })

  it('restores a valid draft and clears it after save', () => {
    const storage = memoryStorage()
    const key = 'staff-access-draft'
    const value = [{ courseId: 'course-math', groupId: null }]
    expect(writeStaffAccessDraft(storage, key, value)).toBe(true)
    expect(readStaffAccessDraft(storage, key, [])).toEqual(value)
    clearStaffAccessDraft(storage, key)
    expect(readStaffAccessDraft(storage, key, [])).toEqual([])
  })

  it('falls back safely when stored JSON is invalid', () => {
    const storage = memoryStorage()
    storage.setItem('draft', '{')
    expect(
      readStaffAccessDraft(storage, 'draft', [
        { courseId: 'course-math', groupId: 'group-beginner' },
      ]),
    ).toEqual([{ courseId: 'course-math', groupId: 'group-beginner' }])
  })
})
