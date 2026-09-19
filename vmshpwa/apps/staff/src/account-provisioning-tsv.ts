import type {
  CourseEnrollmentProvisioningRow,
  FamilyProvisioningRow,
  StudentProvisioningRow,
} from '@vmsh/contracts'

export class ProvisioningTsvError extends Error {
  constructor(
    readonly lineNumber: number,
    message: string,
  ) {
    super(`Строка ${lineNumber}: ${message}`)
  }
}

function lines(source: string) {
  const result = source
    .split(/\r?\n/)
    .map((line, index) => ({ cells: line.split('\t').map((cell) => cell.trim()), index }))
    .filter(({ cells }) => cells.some(Boolean))
  if (result.length === 0) throw new ProvisioningTsvError(1, 'вставьте хотя бы одну строку')
  if (result.length > 2_000) throw new ProvisioningTsvError(2_001, 'не больше 2000 строк за раз')
  return result
}

function dateValue(value: string, lineNumber: number) {
  if (!value) return undefined
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return value
  const match = /^(\d{1,2})\.(\d{1,2})\.(\d{4})$/.exec(value)
  if (!match)
    throw new ProvisioningTsvError(lineNumber, 'дата должна быть ГГГГ-ММ-ДД или ДД.ММ.ГГГГ')
  return `${match[3]}-${match[2]!.padStart(2, '0')}-${match[1]!.padStart(2, '0')}`
}

export function parseStudentProvisioningTsv(source: string): StudentProvisioningRow[] {
  return lines(source).map(({ cells, index }) => {
    const lineNumber = index + 1
    if (cells.length !== 7) {
      throw new ProvisioningTsvError(lineNumber, 'нужно 7 столбцов, разделённых табуляцией')
    }
    const [surname, name, patronymic, birthDate, gradeText, login, password] = cells
    if (!surname || !name || !login || !password) {
      throw new ProvisioningTsvError(lineNumber, 'фамилия, имя, логин и пароль обязательны')
    }
    let grade: number | undefined
    if (gradeText) {
      grade = Number(gradeText)
      if (!Number.isInteger(grade) || grade < 1 || grade > 11) {
        throw new ProvisioningTsvError(lineNumber, 'класс должен быть целым числом от 1 до 11')
      }
    }
    return {
      surname,
      name,
      ...(patronymic ? { patronymic } : {}),
      ...(birthDate ? { birthDate: dateValue(birthDate, lineNumber) } : {}),
      ...(grade === undefined ? {} : { grade }),
      login,
      password,
    }
  })
}

export function parseFamilyProvisioningTsv(source: string): FamilyProvisioningRow[] {
  return lines(source).map(({ cells, index }) => {
    const lineNumber = index + 1
    if (cells.length !== 5) {
      throw new ProvisioningTsvError(lineNumber, 'нужно 5 столбцов, разделённых табуляцией')
    }
    const [name, login, password, emails, childLoginsText] = cells
    if (!name || !login || !password || !emails || !childLoginsText) {
      throw new ProvisioningTsvError(lineNumber, 'все пять столбцов обязательны')
    }
    const childLogins = childLoginsText
      .split(',')
      .map((value) => value.trim())
      .filter(Boolean)
    if (childLogins.length === 0) {
      throw new ProvisioningTsvError(lineNumber, 'укажите хотя бы один логин ребёнка')
    }
    return { name, login, password, emails, childLogins }
  })
}

export function serializeStudentProvisioningTsv(rows: StudentProvisioningRow[]): string {
  return rows
    .map((row) =>
      [
        row.surname,
        row.name,
        row.patronymic ?? '',
        row.birthDate ?? '',
        row.grade?.toString() ?? '',
        row.login,
        row.password,
      ].join('\t'),
    )
    .join('\n')
}

export function serializeFamilyProvisioningTsv(rows: FamilyProvisioningRow[]): string {
  return rows
    .map((row) =>
      [
        row.name,
        row.login,
        row.password,
        Array.isArray(row.emails) ? row.emails.join(', ') : row.emails,
        row.childLogins.join(', '),
      ].join('\t'),
    )
    .join('\n')
}

export function parseCourseEnrollmentProvisioningTsv(
  source: string,
): CourseEnrollmentProvisioningRow[] {
  return lines(source).map(({ cells, index }) => {
    const lineNumber = index + 1
    if (cells.length !== 3) {
      throw new ProvisioningTsvError(lineNumber, 'нужно 3 столбца, разделённых табуляцией')
    }
    const [login, courseCode, allowedGroupsText] = cells
    if (!login || !courseCode || !allowedGroupsText) {
      throw new ProvisioningTsvError(lineNumber, 'все три столбца обязательны')
    }
    const allowedGroupCodes = allowedGroupsText
      .split(/[,;]/)
      .map((value) => value.trim())
      .filter(Boolean)
    if (allowedGroupCodes.length === 0) {
      throw new ProvisioningTsvError(lineNumber, 'укажите хотя бы одну доступную группу')
    }
    return { login, courseCode, allowedGroupCodes }
  })
}

export function provisioningDraftKey(
  storageNamespace: string,
  accountId: string,
  audience: 'student' | 'family' | 'course-enrollment',
) {
  return `${storageNamespace}:draft:${accountId}:provision-${audience}`
}
