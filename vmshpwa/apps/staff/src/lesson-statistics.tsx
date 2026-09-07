import { DistributionViolin, StrengthTrend } from '@vmsh/product'
import type { StaffStatisticsResponse } from '@vmsh/contracts'
import {
  Button,
  Label,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@vmsh/ui'

/** Live facts and model snapshots stay distinct; see docs/lesson-statistics.md. */
export function LessonStatistics({
  data,
  onLessonChange,
  studentId,
  onStudentChange,
  onRefresh,
}: {
  data: StaffStatisticsResponse
  onLessonChange: (lesson: number) => void
  studentId: string | null
  onStudentChange: (student: string | null) => void
  onRefresh: () => void
}) {
  const lesson = data.basicLesson
  const maximum = Math.max(1, ...(lesson?.groups.map((g) => g.problems.length) ?? []))
  return (
    <section className="space-y-4" aria-label="Статистика по отправленным задачам">
      <div className="flex flex-wrap items-end gap-3">
        <Label>
          Занятие
          <select
            className="ml-2 rounded border border-input bg-surface p-2"
            value={lesson?.lessonNumber ?? ''}
            onChange={(e) => onLessonChange(Number(e.target.value))}
          >
            {!data.lessonNumbers.length && <option value="">Нет опубликованных занятий</option>}
            {data.lessonNumbers.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </Label>
        <Button onClick={onRefresh} variant="outline">
          Обновить статистику
        </Button>
      </div>
      <p className="text-small text-muted-foreground">
        Зачёт — 1 балл, половина — 0,5. Участники — все отправлявшие задачи этой группы занятия,
        включая тех, у кого пока 0 баллов.
      </p>
      <div className="flex flex-wrap gap-6">
        {lesson?.groups.map((group, index) => (
          <div key={group.groupId} className="w-52">
            {group.distribution.length === 0 ? (
              <p>{group.name}: пока нет отправок</p>
            ) : group.distribution.length === 1 ? (
              <figure>
                <svg
                  viewBox="0 0 100 120"
                  role="img"
                  aria-label={`${group.name}: один участник, ${group.distribution[0]} баллов`}
                  className="h-40 w-full"
                >
                  <circle
                    cx="50"
                    cy={110 - ((group.distribution[0] ?? 0) / maximum) * 100}
                    r="4"
                    className="fill-chart-1"
                  />
                </svg>
                <figcaption>
                  {group.name}: {group.distribution[0]} баллов
                </figcaption>
              </figure>
            ) : (
              <DistributionViolin
                colorIndex={index % 3 === 0 ? 1 : index % 3 === 1 ? 2 : 3}
                values={group.distribution}
                domain={[0, maximum]}
                caption={`${group.name} · ${group.participantCount} участников · баллы`}
              />
            )}
          </div>
        ))}
      </div>
      {lesson?.groups.map((group) => (
        <section key={group.groupId} className="space-y-2">
          <h2 className="font-semibold">
            {group.name} · занятие {lesson.lessonNumber}
          </h2>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  {[
                    'Задача',
                    'Название',
                    'Баллы',
                    'Пробовали',
                    'Участников',
                    'Доля',
                    'Сложность для слабых',
                    'Сложность для сильных',
                  ].map((label) => (
                    <TableHead key={label}>{label}</TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {group.problems.map((problem) => (
                  <TableRow key={problem.problemId}>
                    <TableCell>{problem.label}</TableCell>
                    <TableCell>{problem.title}</TableCell>
                    <TableCell>{problem.points.toLocaleString('ru-RU')}</TableCell>
                    <TableCell>{problem.tried}</TableCell>
                    <TableCell>{group.participantCount}</TableCell>
                    <TableCell
                      className={
                        problem.share === null
                          ? ''
                          : problem.share >= 70
                            ? 'bg-chart-1/20'
                            : problem.share >= 40
                              ? 'bg-chart-2/20'
                              : 'bg-chart-3/20'
                      }
                    >
                      {problem.share === null ? '—' : `${problem.share.toFixed(1)}%`}
                    </TableCell>
                    {[problem.difficultyWeak, problem.difficultyStrong].map((value, index) => (
                      <TableCell key={index}>
                        {value === null ? 'Ещё не рассчитано' : value.toFixed(3)}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </section>
      ))}
      <Label>
        График школьника
        <select
          className="ml-2 rounded border border-input bg-surface p-2"
          value={studentId ?? ''}
          onChange={(e) => onStudentChange(e.target.value || null)}
        >
          <option value="">Выберите школьника</option>
          {data.students.map((s) => (
            <option key={s.studentId} value={s.studentId}>
              {s.name}
            </option>
          ))}
        </select>
      </Label>
      {studentId &&
        (data.personal.length ? (
          <StrengthTrend
            points={data.personal.map((p) => ({
              lesson: String(p.lessonNumber),
              simple: p.simple,
              complex: p.complex,
              difficulty: p.difficulty,
              simpleSmooth: p.simpleSmooth ?? p.simple,
              complexSmooth: p.complexSmooth ?? p.complex,
              group: p.groupCode,
              solved: `${p.solved}/${p.total}`,
            }))}
          />
        ) : (
          <p>Для школьника пока нет расчёта силы по занятиям от 1.</p>
        ))}
      {data.run && (
        <p className="text-caption text-muted-foreground">
          Сложности и сила рассчитаны:{' '}
          {new Date(data.run.completedAt).toLocaleString('ru-RU', { timeZone: 'Europe/Moscow' })}{' '}
          МСК
        </p>
      )}
    </section>
  )
}
