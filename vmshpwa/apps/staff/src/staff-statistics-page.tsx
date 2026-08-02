import { BarChart3, CalendarDays, UsersRound } from 'lucide-react'
import { useMemo } from 'react'

import {
  PageLayout,
  PageSection,
  PageStatePanel,
  createStaffStatisticsClient,
  useAuthenticatedPrincipal,
  useAuthentication,
  useStaffStatisticsQuery,
} from '@vmsh/app-shell'
import {
  ApiResponseError,
  type StaffStatisticsLesson,
  type StaffStatisticsResponse,
} from '@vmsh/contracts'
import { DistributionViolin } from '@vmsh/product'
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Label,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@vmsh/ui'

/*
 * Staff aggregate reporting follows development-plan/14-phase-10-admin-and-google-exit.md.
 * This page deliberately consumes an immutable analytics run: it never derives a pupil's
 * position in a cohort and never exposes row-level student data. Contract coverage lives in
 * packages/contracts/src/staff-statistics.test.ts; the real API is covered by
 * pwa_tests/integration/test_phase10_staff_statistics.py.
 */

function formatMetric(value: number | null, suffix = ''): string {
  return value === null
    ? '—'
    : `${value.toLocaleString('ru-RU', { maximumFractionDigits: 1 })}${suffix}`
}

function formatRunDate(value: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    dateStyle: 'long',
    timeStyle: 'short',
    timeZone: 'Europe/Moscow',
  }).format(new Date(value))
}

function selectedLesson(
  lessons: StaffStatisticsLesson[],
  lessonNumber: number | null,
): StaffStatisticsLesson | null {
  if (lessons.length === 0) return null
  return lessons.find((lesson) => lesson.lessonNumber === lessonNumber) ?? lessons.at(-1) ?? null
}

function MetricCard({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof UsersRound
  label: string
  value: string
}) {
  return (
    <Card size="sm">
      <CardHeader className="grid grid-cols-[1fr_auto] items-center">
        <CardTitle className="text-caption font-medium text-muted-foreground">{label}</CardTitle>
        <Icon aria-hidden="true" className="size-4 text-muted-foreground" />
      </CardHeader>
      <CardContent className="font-num text-title font-semibold">{value}</CardContent>
    </Card>
  )
}

export function StaffStatisticsView({
  data,
  lessonNumber,
  onCourseChange,
  onGroupChange,
  onLessonChange,
}: {
  data: StaffStatisticsResponse
  lessonNumber: number | null
  onCourseChange: (courseId: string) => void
  onGroupChange: (groupId: string | null) => void
  onLessonChange: (lessonNumber: number) => void
}) {
  const course = data.courses.find((item) => item.courseId === data.selectedCourseId) ?? null
  const lesson = selectedLesson(data.lessons, lessonNumber)
  const distributionMaximum = Math.max(1, ...(lesson?.solvedDistribution ?? [1]))

  return (
    <PageLayout
      actions={
        <div className="grid min-w-64 gap-2 sm:grid-cols-2">
          <Label className="grid gap-1 text-caption">
            Курс
            <select
              aria-label="Курс"
              className="min-h-9 rounded-md border border-input bg-surface px-3 text-small"
              onChange={(event) => onCourseChange(event.currentTarget.value)}
              value={data.selectedCourseId ?? ''}
            >
              {data.courses.length === 0 ? <option value="">Нет доступных курсов</option> : null}
              {data.courses.map((item) => (
                <option key={item.courseId} value={item.courseId}>
                  {item.name}
                </option>
              ))}
            </select>
          </Label>
          <Label className="grid gap-1 text-caption">
            Группа
            <select
              aria-label="Группа"
              className="min-h-9 rounded-md border border-input bg-surface px-3 text-small"
              disabled={course === null}
              onChange={(event) => onGroupChange(event.currentTarget.value || null)}
              value={data.selectedGroupId ?? ''}
            >
              <option value="">Все доступные</option>
              {course?.groups.map((group) => (
                <option key={group.groupId} value={group.groupId}>
                  {group.name}
                </option>
              ))}
            </select>
          </Label>
        </div>
      }
      description="Анонимные агрегаты по завершённым занятиям. Здесь нет рейтинга школьников и сравнения конкретного ребёнка с группой."
      title="Статистика курса"
      width="wide"
    >
      {data.courses.length === 0 ? (
        <PageStatePanel
          description="Администратор ещё не выдал вам доступ к курсу со статистикой."
          state="empty"
          title="Нет доступных курсов"
        />
      ) : data.run === null || data.lessons.length === 0 || lesson === null ? (
        <PageStatePanel
          description="Первый завершённый расчёт появится здесь автоматически. Исходные результаты при этом не изменяются."
          state="empty"
          title="Расчётов пока нет"
        />
      ) : (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center gap-2 text-caption text-muted-foreground">
            <Badge variant="neutral">{course?.name ?? 'Курс'}</Badge>
            <span>
              Расчёт {data.run.algorithm} · версия {data.run.algorithmVersion}
            </span>
            <span aria-hidden="true">·</span>
            <span>{formatRunDate(data.run.completedAt)} МСК</span>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard
              icon={CalendarDays}
              label="Выбрано занятие"
              value={`№ ${lesson.lessonNumber}`}
            />
            <MetricCard
              icon={UsersRound}
              label="Школьников в агрегате"
              value={String(lesson.studentCount)}
            />
            <MetricCard
              icon={BarChart3}
              label="Среднее число решённых"
              value={formatMetric(lesson.meanSolvedItems)}
            />
            <MetricCard
              icon={BarChart3}
              label="Доля решённых задач"
              value={formatMetric(lesson.completionRate, '%')}
            />
          </div>

          <PageSection
            description="Строки относятся к одному зафиксированному расчёту; выбор занятия сохраняется в адресе страницы."
            title="Занятия"
          >
            <div className="overflow-x-auto rounded-lg border border-border bg-surface">
              <Table className="min-w-[48rem]">
                <TableHeader>
                  <TableRow>
                    <TableHead>Занятие</TableHead>
                    <TableHead>Группы</TableHead>
                    <TableHead className="text-right">Школьники</TableHead>
                    <TableHead className="text-right">Простые</TableHead>
                    <TableHead className="text-right">Сложные</TableHead>
                    <TableHead className="text-right">Решено</TableHead>
                    <TableHead className="text-right">Доля</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.lessons.map((item) => {
                    const active = item.lessonNumber === lesson.lessonNumber
                    return (
                      <TableRow
                        data-state={active ? 'selected' : undefined}
                        key={item.lessonNumber}
                      >
                        <TableCell>
                          <Button
                            aria-current={active ? 'true' : undefined}
                            onClick={() => onLessonChange(item.lessonNumber)}
                            size="sm"
                            variant={active ? 'secondary' : 'ghost'}
                          >
                            Занятие {item.lessonNumber}
                          </Button>
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-wrap gap-1">
                            {item.groups.map((group) => (
                              <Badge key={group.groupId} variant="neutral">
                                {group.code} · {group.studentCount}
                              </Badge>
                            ))}
                          </div>
                        </TableCell>
                        <TableCell className="text-right font-num">{item.studentCount}</TableCell>
                        <TableCell className="text-right font-num">
                          {formatMetric(item.meanSimpleStrength)}
                        </TableCell>
                        <TableCell className="text-right font-num">
                          {formatMetric(item.meanComplexStrength)}
                        </TableCell>
                        <TableCell className="text-right font-num">
                          {formatMetric(item.meanSolvedItems)}
                        </TableCell>
                        <TableCell className="text-right font-num">
                          {formatMetric(item.completionRate, '%')}
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            </div>
          </PageSection>

          <PageSection
            description="Распределение обезличено: график не содержит маркера или позиции отдельного школьника."
            title={`Занятие ${lesson.lessonNumber}`}
          >
            <div className="grid gap-4 lg:grid-cols-[minmax(15rem,22rem)_1fr]">
              <Card>
                <CardHeader>
                  <CardTitle>Сколько задач решено</CardTitle>
                </CardHeader>
                <CardContent>
                  <DistributionViolin
                    caption={`Распределение по ${lesson.studentCount} школьникам.`}
                    domain={[0, distributionMaximum]}
                    values={lesson.solvedDistribution}
                  />
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>Состав агрегата</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {lesson.groups.map((group) => (
                    <div
                      className="flex items-center justify-between gap-4 border-b border-border py-2 last:border-0"
                      key={group.groupId}
                    >
                      <div>
                        <div className="font-medium">{group.name}</div>
                        <div className="text-caption text-muted-foreground">Код {group.code}</div>
                      </div>
                      <span className="font-num text-small">{group.studentCount}</span>
                    </div>
                  ))}
                </CardContent>
              </Card>
            </div>
          </PageSection>
        </div>
      )}
    </PageLayout>
  )
}

export function StaffStatisticsPage({
  courseId,
  groupId,
  lessonNumber,
  onCourseChange,
  onGroupChange,
  onLessonChange,
}: {
  courseId: string | null
  groupId: string | null
  lessonNumber: number | null
  onCourseChange: (courseId: string) => void
  onGroupChange: (groupId: string | null) => void
  onLessonChange: (lessonNumber: number) => void
}) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'staff') throw new Error('Statistics requires Staff auth')
  const client = useMemo(
    () =>
      createStaffStatisticsClient(authentication.client.runtime, {
        refreshSession: async () => {
          try {
            return await authentication.refresh()
          } catch (error) {
            authentication.handleApiError(error)
            throw error
          }
        },
      }),
    [authentication],
  )
  const result = useStaffStatisticsQuery(
    client,
    { audience: 'staff', accountId: principal.accountId },
    { courseId, groupId },
  )

  if (result.isPending) {
    return (
      <PageLayout title="Статистика курса" width="wide">
        <PageStatePanel state="loading" />
      </PageLayout>
    )
  }
  if (result.error) {
    return (
      <PageLayout title="Статистика курса" width="wide">
        <PageStatePanel
          actionLabel="Повторить"
          onAction={() => void result.refetch()}
          state={
            result.error instanceof ApiResponseError && result.error.status === 403
              ? 'forbidden'
              : 'error'
          }
        />
      </PageLayout>
    )
  }
  return (
    <StaffStatisticsView
      data={result.data}
      lessonNumber={lessonNumber}
      onCourseChange={onCourseChange}
      onGroupChange={onGroupChange}
      onLessonChange={onLessonChange}
    />
  )
}
