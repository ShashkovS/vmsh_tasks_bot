import { useId, useMemo, useState } from 'react'
import { Button, Input, Label } from '@vmsh/ui'
import { studentNameMatchesSearch } from './student-directory-search'

/** Bounded local directory search; see docs/lesson-statistics.md. */
export function StatisticsStudentSearch({
  students,
  studentId,
  onChange,
  label = 'График школьника',
}: {
  students: { studentId: string; name: string }[]
  studentId: string | null
  onChange: (id: string | null) => void
  label?: string
}) {
  const id = useId()
  const [query, setQuery] = useState('')
  const matches = useMemo(
    () =>
      query.trim()
        ? students.filter((student) => studentNameMatchesSearch(student.name, query))
        : [],
    [students, query],
  )
  const selected = students.find((student) => student.studentId === studentId)
  return (
    <section className="max-w-lg space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        type="search"
        value={query}
        placeholder="Фамилия или имя, можно с опечаткой"
        onChange={(event) => setQuery(event.target.value)}
      />
      {selected && (
        <div className="flex items-center gap-2">
          <span>Выбран: {selected.name}</span>
          <Button
            variant="ghost"
            onClick={() => {
              setQuery('')
              onChange(null)
            }}
          >
            Сбросить выбор
          </Button>
        </div>
      )}
      {query.trim() && (
        <>
          <p role="status" className="text-small text-muted-foreground">
            {matches.length
              ? `Найдено: ${matches.length}${matches.length > 20 ? '. Показаны первые 20 — уточните имя или фамилию.' : ''}`
              : 'Школьники не найдены'}
          </p>
          <ul aria-label="Найденные школьники" className="max-h-64 overflow-y-auto">
            {matches.slice(0, 20).map((student) => (
              <li key={student.studentId}>
                <Button
                  variant="ghost"
                  className="w-full justify-start"
                  onClick={() => {
                    setQuery('')
                    onChange(student.studentId)
                  }}
                >
                  {student.name}
                </Button>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}
