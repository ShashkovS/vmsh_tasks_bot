import type { CreateStaffMemberBatchRequest } from '@vmsh/contracts'

export type TeacherBatchRow = CreateStaffMemberBatchRequest['rows'][number]

export class TeacherBatchTsvError extends Error {
  constructor(
    readonly lineNumber: number,
    message: string,
  ) {
    super(`Строка ${lineNumber}: ${message}`)
  }
}

export function parseTeacherBatchTsv(source: string): TeacherBatchRow[] {
  const lines = source
    .split(/\r?\n/)
    .map((line, index) => ({ cells: line.split('\t').map((cell) => cell.trim()), index }))
    .filter(({ cells }) => cells.some(Boolean))
  if (lines.length === 0) throw new TeacherBatchTsvError(1, 'вставьте хотя бы одну строку')
  if (lines.length > 500) throw new TeacherBatchTsvError(501, 'не больше 500 строк за раз')

  const usernames = new Set<string>()
  return lines.map(({ cells, index }) => {
    const lineNumber = index + 1
    if (cells.length !== 5) {
      throw new TeacherBatchTsvError(lineNumber, 'нужно 5 столбцов, разделённых табуляцией')
    }
    const [surname, name, middleName, username, password] = cells
    if (!surname || !name || !username || !password) {
      throw new TeacherBatchTsvError(lineNumber, 'фамилия, имя, логин и пароль обязательны')
    }
    if (surname.length > 100 || name.length > 100 || (middleName?.length ?? 0) > 100) {
      throw new TeacherBatchTsvError(lineNumber, 'ФИО не должно быть длиннее 100 символов')
    }
    if (username.length > 100) {
      throw new TeacherBatchTsvError(lineNumber, 'логин не должен быть длиннее 100 символов')
    }
    if (password.length < 8 || password.length > 256) {
      throw new TeacherBatchTsvError(lineNumber, 'пароль должен содержать от 8 до 256 символов')
    }
    const normalizedUsername = username.normalize('NFKC').toLocaleLowerCase('ru')
    if (usernames.has(normalizedUsername)) {
      throw new TeacherBatchTsvError(lineNumber, 'логин повторяется в этой таблице')
    }
    usernames.add(normalizedUsername)
    return { surname, name, middleName: middleName || null, username, password }
  })
}

export function teacherBatchDraftKey(storageNamespace: string, accountId: string): string {
  return `${storageNamespace}:draft:${accountId}:teacher-batch`
}
