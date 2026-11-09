import { describe, expect, it } from 'vitest'

import type { AdminStudentDirectoryEntry } from '@vmsh/contracts'

import { filterStudents, studentMatchesSearch } from './student-directory-search'

const student = {
  studentId: 'student-shashkov',
  surname: 'Шашков',
  name: 'Сергей',
  middleName: 'Игоревич',
  grade: 7,
  birthday: null,
  strength: 8.1,
  usernameSuggestion: null,
  webAccount: null,
  familyAccounts: [],
  enrollments: [],
} satisfies AdminStudentDirectoryEntry

describe('Student directory search', () => {
  it.each(['шаш', 'СЕРГЕЙ ШАШКОВ', 'серг шаш', 'шашкоф', 'игоревеч'])(
    'finds a student by fragment, reordered words or a small typo: %s',
    (query) => expect(studentMatchesSearch(student, query)).toBe(true),
  )

  it('normalizes ё, е and extra spaces', () => {
    const withYo = { ...student, surname: 'Соловьёв' }
    expect(studentMatchesSearch(withYo, '  соловьев  ')).toBe(true)
  })

  it('does not turn an unrelated short query into a fuzzy match', () => {
    expect(studentMatchesSearch(student, 'ив')).toBe(false)
    expect(filterStudents([student], 'Петров')).toEqual([])
  })
})
