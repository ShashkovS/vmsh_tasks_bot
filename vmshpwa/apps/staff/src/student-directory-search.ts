import type { AdminStudentDirectoryEntry } from '@vmsh/contracts'

function normalize(value: string): string {
  return value
    .normalize('NFKC')
    .toLocaleLowerCase('ru-RU')
    .replaceAll('ё', 'е')
    .trim()
    .replaceAll(/\s+/g, ' ')
}

function editDistance(left: string, right: string): number {
  const previous = Array.from({ length: right.length + 1 }, (_, index) => index)
  for (let leftIndex = 1; leftIndex <= left.length; leftIndex += 1) {
    const current = [leftIndex]
    for (let rightIndex = 1; rightIndex <= right.length; rightIndex += 1) {
      current[rightIndex] = Math.min(
        current[rightIndex - 1]! + 1,
        previous[rightIndex]! + 1,
        previous[rightIndex - 1]! + (left[leftIndex - 1] === right[rightIndex - 1] ? 0 : 1),
      )
    }
    previous.splice(0, previous.length, ...current)
  }
  return previous[right.length]!
}

function tokenMatches(query: string, candidate: string): boolean {
  if (candidate.includes(query)) return true
  if (query.length < 3) return false
  const tolerance = query.length <= 5 ? 1 : query.length <= 9 ? 2 : 3
  return editDistance(query, candidate) <= tolerance
}

export function studentMatchesSearch(
  student: AdminStudentDirectoryEntry,
  rawQuery: string,
): boolean {
  return studentNameMatchesSearch(
    [student.surname, student.name, student.middleName ?? ''].filter(Boolean).join(' '),
    rawQuery,
  )
}

export function studentNameMatchesSearch(displayName: string, rawQuery: string): boolean {
  const query = normalize(rawQuery)
  if (!query) return true
  const name = normalize(displayName)
  if (name.includes(query)) return true
  const candidateTokens = name.split(' ')
  return query
    .split(' ')
    .every((queryToken) => candidateTokens.some((candidate) => tokenMatches(queryToken, candidate)))
}

export function filterStudents(
  students: AdminStudentDirectoryEntry[],
  query: string,
): AdminStudentDirectoryEntry[] {
  return students.filter((student) => studentMatchesSearch(student, query))
}
