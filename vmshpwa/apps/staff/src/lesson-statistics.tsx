import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { formatDateTime, formatNumber } from '@vmsh/i18n'
import type { ReactNode } from 'react'
import { DistributionViolin, StrengthTrend } from '@vmsh/product'
import type { StaffStatisticsResponse } from '@vmsh/contracts'
import { StatisticsStudentSearch } from './statistics-student-search'
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
  recalculationControl,
}: {
  data: StaffStatisticsResponse
  onLessonChange: (lesson: number) => void
  studentId: string | null
  onStudentChange: (student: string | null) => void
  onRefresh: () => void
  recalculationControl?: ReactNode
}) {
  const lesson = data.basicLesson
  const maximum = Math.max(1, ...(lesson?.groups.map((g) => g.problems.length) ?? []))
  return (
    <section className="space-y-4" aria-label={t`Статистика по отправленным задачам`}>
      <div className="flex flex-wrap items-start gap-3">
        <Label>
          <Trans>Занятие</Trans>
          <select
            className="ml-2 rounded border border-input bg-surface p-2"
            value={lesson?.lessonNumber ?? ''}
            onChange={(e) => onLessonChange(Number(e.target.value))}
          >
            {!data.lessonNumbers.length && (
              <option value="">
                <Trans>Нет опубликованных занятий</Trans>
              </option>
            )}
            {data.lessonNumbers.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </Label>
        <Button onClick={onRefresh} variant="outline">
          <Trans>Обновить статистику</Trans>
        </Button>
        {recalculationControl}
      </div>
      <div className="flex flex-wrap gap-6">
        {lesson?.groups.map((group, index) => (
          <div key={group.groupId} className="w-55">
            {group.distribution.length === 0 ? (
              <p>
                <Trans>{group.name}: пока нет отправок</Trans>
              </p>
            ) : group.distribution.length === 1 ? (
              <figure>
                <svg
                  viewBox="0 0 220 260"
                  role="img"
                  aria-label={t`${group.name}: один участник, число решённых задач ${group.distribution[0] ?? 0}`}
                  className="h-65 w-full"
                >
                  <circle
                    cx="110"
                    cy={248 - ((group.distribution[0] ?? 0) / maximum) * 236}
                    r="4"
                    className="fill-chart-1"
                  />
                </svg>
                <figcaption>
                  <Trans>{group.name} · 1 участник</Trans>
                </figcaption>
              </figure>
            ) : (
              <DistributionViolin
                bandwidth={0.5}
                height={260}
                valueLabel={t`Число решённых задач`}
                colorIndex={index % 3 === 0 ? 1 : index % 3 === 1 ? 2 : 3}
                values={group.distribution}
                domain={[0, maximum]}
                caption={t`${group.name} · ${group.participantCount} участников`}
              />
            )}
          </div>
        ))}
      </div>
      {lesson?.groups.map((group) => (
        <section key={group.groupId} className="space-y-2">
          <h2 className="font-semibold">
            <Trans>
              {group.name} · занятие {lesson.lessonNumber}
            </Trans>
          </h2>
          <div className="overflow-x-auto">
            <Table className="lesson-statistics-table">
              <TableHeader>
                <TableRow>
                  {[
                    { align: 'left', label: t`Задача` },
                    { align: 'left', label: t`Название` },
                    { align: 'right', label: t`Решили` },
                    { align: 'right', label: t`Пробовали` },
                    { align: 'right', label: t`Участников` },
                    { align: 'right', label: t`Доля` },
                    { align: 'right', label: t`Сложность для слабых` },
                    { align: 'right', label: t`Сложность для сильных` },
                  ].map(({ align, label }) => (
                    <TableHead className={align === 'left' ? '' : 'text-right'} key={label}>
                      {label}
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {group.problems.map((problem) => (
                  <TableRow key={problem.problemId}>
                    <TableCell>{problem.label}</TableCell>
                    <TableCell>{problem.title}</TableCell>
                    <TableCell>{formatNumber(problem.points)}</TableCell>
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
                        {value === null ? t`Ещё не рассчитано` : value.toFixed(3)}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </section>
      ))}
      <StatisticsStudentSearch
        students={data.students}
        studentId={studentId}
        onChange={onStudentChange}
      />
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
          <p>
            <Trans>Для школьника пока нет расчёта силы по занятиям от 1.</Trans>
          </p>
        ))}
      {data.run && (
        <p className="text-caption text-muted-foreground">
          <Trans>Сложности и сила рассчитаны: </Trans>
          {formatDateTime(new Date(data.run.completedAt), { timeZone: 'Europe/Moscow' })}
          <Trans> МСК</Trans>
        </p>
      )}
    </section>
  )
}
