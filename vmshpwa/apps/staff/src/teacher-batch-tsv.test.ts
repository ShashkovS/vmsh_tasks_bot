import { describe, expect, it } from 'vitest'

import { parseTeacherBatchTsv } from './teacher-batch-tsv'

describe('teacher TSV batch', () => {
  it('parses five spreadsheet columns and keeps the password write-only in the row', () => {
    expect(parseTeacherBatchTsv('Иванова\tМария\tПетровна\tteacher01\tQwerty01')).toEqual([
      {
        surname: 'Иванова',
        name: 'Мария',
        middleName: 'Петровна',
        username: 'teacher01',
        password: 'Qwerty01',
      },
    ])
  })

  it('rejects a duplicate login after Unicode normalization', () => {
    expect(() =>
      parseTeacherBatchTsv(
        'Иванова\tМария\t\tTeacher01\tQwerty01\nПетров\tИван\t\tteacher01\tQwerty02',
      ),
    ).toThrow('логин повторяется')
  })
})
