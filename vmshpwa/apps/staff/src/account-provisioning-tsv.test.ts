import { describe, expect, it } from 'vitest'

import {
  ProvisioningTsvError,
  parseCourseEnrollmentProvisioningTsv,
  parseFamilyProvisioningTsv,
  parseStudentProvisioningTsv,
  provisioningDraftKey,
  serializeFamilyProvisioningTsv,
  serializeStudentProvisioningTsv,
} from './account-provisioning-tsv'

describe('account provisioning TSV', () => {
  it('parses Student spreadsheet rows and normalizes a Russian date', () => {
    expect(
      parseStudentProvisioningTsv(
        'Иванов\tИван\tИванович\t05.04.2013\t7\tivanov\tTelegramToken\n' +
          'Петрова\tАнна\t\t\t\tpetrova\tqwerty-test',
      ),
    ).toEqual([
      {
        surname: 'Иванов',
        name: 'Иван',
        patronymic: 'Иванович',
        birthDate: '2013-04-05',
        grade: 7,
        login: 'ivanov',
        password: 'TelegramToken',
      },
      { surname: 'Петрова', name: 'Анна', login: 'petrova', password: 'qwerty-test' },
    ])
  })

  it('parses Family emails and several child logins', () => {
    expect(
      parseFamilyProvisioningTsv(
        'Семья Ивановых\tparent\tqwerty-family\tone@example.org, two@example.org\tivanov, petrova',
      ),
    ).toEqual([
      {
        name: 'Семья Ивановых',
        login: 'parent',
        password: 'qwerty-family',
        emails: 'one@example.org, two@example.org',
        childLogins: ['ivanov', 'petrova'],
      },
    ])
  })

  it('serializes skipped rows back to editable TSV without losing optional columns', () => {
    expect(
      serializeStudentProvisioningTsv([
        {
          surname: 'Иванов',
          name: 'Иван',
          birthDate: '2013-04-05',
          login: 'ivanov',
          password: 'token',
        },
      ]),
    ).toBe('Иванов\tИван\t\t2013-04-05\t\tivanov\ttoken')
    expect(
      serializeFamilyProvisioningTsv([
        {
          name: 'Семья Ивановых',
          login: 'parent',
          password: 'password',
          emails: ['one@example.org', 'two@example.org'],
          childLogins: ['ivanov', 'petrova'],
        },
      ]),
    ).toBe('Семья Ивановых\tparent\tpassword\tone@example.org, two@example.org\tivanov, petrova')
  })

  it('reports the exact malformed line and scopes drafts to an account', () => {
    expect(() => parseStudentProvisioningTsv('Иванов\tИван')).toThrow(
      new ProvisioningTsvError(1, 'нужно 7 столбцов, разделённых табуляцией'),
    )
    expect(provisioningDraftKey('vmsh:staff:agent', 'admin.one', 'student')).toBe(
      'vmsh:staff:agent:draft:admin.one:provision-student',
    )
  })

  it('parses a separate course enrollment batch with comma or semicolon groups', () => {
    expect(
      parseCourseEnrollmentProvisioningTsv('ivanov\tmath-57\tэ, н, п\npetrova\tphysics\tф1; ф2'),
    ).toEqual([
      {
        login: 'ivanov',
        courseCode: 'math-57',
        allowedGroupCodes: ['э', 'н', 'п'],
      },
      {
        login: 'petrova',
        courseCode: 'physics',
        allowedGroupCodes: ['ф1', 'ф2'],
      },
    ])
  })
})
