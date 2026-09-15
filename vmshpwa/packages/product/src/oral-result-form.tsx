import { useId, useMemo, useState } from 'react'

import type { OralResultOutcome, StaffOralRosterResponse } from '@vmsh/contracts'
import {
  Button,
  Card,
  CardContent,
  Input,
  Label,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  cn,
} from '@vmsh/ui'

import { ReactionPicker } from './reaction-picker'
import { reactionsForScope } from './reaction'

export type OralMarkValue = OralResultOutcome | 'unmarked'

export interface OralResultFormProps {
  students: StaffOralRosterResponse['students']
  problems: StaffOralRosterResponse['problems']
  studentId: string
  marks: Record<string, OralMarkValue>
  reactionId: number | null
  busy?: boolean
  onStudentChange: (studentId: string) => void
  onMarkChange: (problemId: string, value: OralMarkValue) => void
  onReactionChange: (reactionId: number | null) => void
  onSubmit: () => void
}

/** Compact teacher flow for one student's online oral round. */
export function OralResultForm({
  students,
  problems,
  studentId,
  marks,
  reactionId,
  busy,
  onStudentChange,
  onMarkChange,
  onReactionChange,
  onSubmit,
}: OralResultFormProps) {
  const searchId = useId()
  const studentIdLabel = useId()
  const [search, setSearch] = useState('')
  const filteredStudents = useMemo(() => {
    const query = search.trim().toLocaleLowerCase('ru-RU')
    if (!query) return students
    return students.filter((student) =>
      student.displayName.toLocaleLowerCase('ru-RU').includes(query),
    )
  }, [search, students])
  const selected = students.find((student) => student.studentId === studentId)
  const markedCount = Object.values(marks).filter((mark) => mark !== 'unmarked').length
  const reactions = reactionsForScope('teacher-oral')

  return (
    <Card className="max-w-3xl">
      <CardContent className="space-y-4 py-4">
        <div className="grid gap-2 sm:grid-cols-[minmax(10rem,0.65fr)_minmax(14rem,1fr)]">
          <div className="space-y-1">
            <Label htmlFor={searchId}>Быстрый поиск</Label>
            <Input
              id={searchId}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Фамилия или имя"
              value={search}
            />
          </div>
          <div className="space-y-1">
            <Label id={studentIdLabel}>Школьник</Label>
            <Select
              disabled={busy}
              onValueChange={(value) => onStudentChange(value ?? '')}
              value={studentId || null}
            >
              <SelectTrigger aria-labelledby={studentIdLabel} className="w-full" size="sm">
                <SelectValue>{selected?.displayName ?? 'Выберите школьника'}</SelectValue>
              </SelectTrigger>
              <SelectContent align="start">
                {filteredStudents.map((student) => (
                  <SelectItem key={student.studentId} value={student.studentId}>
                    {student.displayName}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <fieldset className="space-y-1.5" disabled={busy || !studentId}>
          <legend className="mb-1 text-label font-medium">Задачи</legend>
          {problems.map((problem) => {
            const value = marks[problem.problemId] ?? 'unmarked'
            return (
              <div
                className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2 rounded-md border border-border px-2.5 py-2"
                key={problem.problemId}
              >
                <p className="min-w-0 truncate text-small">
                  <span className="font-num font-semibold">{problem.displayNumber}.</span>{' '}
                  {problem.title}
                </p>
                <div
                  aria-label={`Результат задачи ${problem.displayNumber}`}
                  className="flex gap-1"
                  role="group"
                >
                  {(
                    [
                      ['unmarked', '—', 'Не отмечено'],
                      ['accepted', '+', 'Зачтено'],
                      ['rejected', '−', 'Не зачтено'],
                    ] as const
                  ).map(([option, symbol, label]) => (
                    <button
                      aria-label={`${problem.displayNumber}: ${label}`}
                      aria-pressed={value === option}
                      className={cn(
                        'min-h-7 min-w-8 rounded-md border px-2 font-num text-small font-semibold',
                        value === option
                          ? option === 'accepted'
                            ? 'border-status-success-border bg-status-success-surface text-status-success'
                            : option === 'rejected'
                              ? 'border-status-danger-border bg-status-danger-surface text-status-danger'
                              : 'border-primary bg-primary/10 text-foreground'
                          : 'border-border bg-surface text-muted-foreground hover:bg-surface-subtle',
                      )}
                      key={option}
                      onClick={() => onMarkChange(problem.problemId, option)}
                      type="button"
                    >
                      {symbol}
                    </button>
                  ))}
                </div>
              </div>
            )
          })}
        </fieldset>

        <ReactionPicker
          compact
          disabled={busy || !studentId}
          hotkeys
          legend="Внутренняя пометка"
          onSelect={onReactionChange}
          options={reactions}
          value={reactionId}
        />

        <div className="flex items-center justify-between gap-3 border-t border-border pt-3">
          <p className="text-caption text-muted-foreground">
            Отмечено: {markedCount} из {problems.length}
          </p>
          <Button disabled={busy || !studentId || markedCount === 0} onClick={onSubmit} size="sm">
            {busy ? 'Сохраняем…' : 'Сохранить результаты'}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
