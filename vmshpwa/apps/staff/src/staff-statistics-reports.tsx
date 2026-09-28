import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { useMemo } from 'react'
import { formatNumber } from '@vmsh/i18n'
import {
  PageLayout,
  PageStatePanel,
  useAuthentication,
  useAuthenticatedPrincipal,
  createStatisticsReportsClient,
  useStatisticsReportQuery,
} from '@vmsh/app-shell'
import { ApiResponseError, type StatisticsPlusTable, type StatisticsSummary } from '@vmsh/contracts'
import { Button, Label } from '@vmsh/ui'
import './staff-statistics.css'

// dev/design-system/05-pages-and-flows.md; docs/lesson-statistics.md, Staff reports.
function sourceLabels() {
  return { bot: t`Бот`, written: t`Письменно`, zoom: t`Zoom`, school: t`Очно` }
}

export function PlusMatrix({ data }: { data: StatisticsPlusTable }) {
  const sources = sourceLabels()
  return (
    <>
      <p className="text-small text-muted-foreground">
        <Trans>
          + — зачёт, ½ — частичный зачёт, − — незачёт, … — ожидает проверки; пусто — нет отправок.
        </Trans>
      </p>
      <div className="flex flex-wrap gap-4 text-small" aria-label={t`Источники плюсов`}>
        {Object.entries(sources).map(([key, label]) => (
          <span key={key} className={`statistics-source-${key}`}>
            {label.slice(0, 1)} — {label}
          </span>
        ))}
      </div>
      <p className="text-small">
        <Trans>Школьников: {data.rows.length}</Trans>
      </p>
      <div className="statistics-matrix-scroll">
        <table className="statistics-matrix" aria-label={t`Таблица плюсов`}>
          <thead>
            <tr>
              <th scope="col">
                <Trans>Школьник</Trans>
              </th>
              {data.problems.map((p) => (
                <th scope="col" key={p.problemId} title={p.title}>
                  {p.label}
                </th>
              ))}
              <th scope="col">
                <Trans>Всего</Trans>
              </th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row) => (
              <tr key={row.studentId}>
                <th scope="row">{row.name}</th>
                {row.cells.map((cell, index) => {
                  const score =
                    cell.score === 1
                      ? '+'
                      : cell.score === 0.5
                        ? '½'
                        : cell.attempted && !cell.pending
                          ? '−'
                          : ''
                  const source = cell.source ? sources[cell.source] : ''
                  const description = [
                    data.problems[index]?.label,
                    score,
                    source,
                    cell.pending ? t`Ожидает проверки` : '',
                  ]
                    .filter(Boolean)
                    .join(' · ')
                  return (
                    <td
                      key={data.problems[index]?.problemId}
                      className={cell.source ? `statistics-source-${cell.source}` : undefined}
                      aria-label={description || t`Нет отправок`}
                      title={description}
                    >
                      <span>
                        {score}
                        {cell.pending ? '…' : ''}
                      </span>
                      {cell.score > 0 ? (
                        <small aria-hidden="true">{source.slice(0, 1)}</small>
                      ) : null}
                    </td>
                  )
                })}
                <td className="font-semibold">{formatNumber(row.total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.rows.length === 0 ? (
        <PageStatePanel state="empty" title={t`Пока нет отправок`} />
      ) : null}
    </>
  )
}

export function CourseSummary({ data }: { data: StatisticsSummary }) {
  const columns: [keyof StatisticsSummary['lessons'][number], string][] = [
    ['students', t`Школьники`],
    ['allPlus', t`Всего плюсов`],
    ['botPlus', t`Бот`],
    ['writtenChecked', t`Проверено`],
    ['writtenPending', t`Ожидает проверки`],
    ['writtenTotal', t`Всего с учётом ожидающих`],
    ['writtenPlus', t`Письменные плюсы`],
    ['writtenWrittenPlus', t`За письменные задачи`],
    ['writtenOralPlus', t`За устные задачи`],
    ['zoomPlus', t`Плюсы Zoom`],
    ['schoolPlus', t`Очные плюсы`],
    ['writtenStudents', t`Школьники: письменно`],
    ['zoomStudents', t`Школьники: Zoom`],
    ['schoolStudents', t`Школьники: очно`],
  ]
  return (
    <>
      <p className="text-small text-muted-foreground">
        <Trans>
          Каждая письменная проверка учитывается отдельно, включая повторные. Непроверенные работы
          добавляют одну единицу на пару школьник–задача. Плюсы отражают текущие оценки.
        </Trans>
      </p>
      <div className="overflow-x-auto">
        <table className="statistics-summary" aria-label={t`Сводка курса`}>
          <thead>
            <tr>
              <th scope="col">
                <Trans>Занятие</Trans>
              </th>
              {columns.map(([key, label]) => (
                <th scope="col" key={key}>
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.lessons.map((row) => (
              <tr key={row.lessonNumber}>
                <th scope="row">{row.lessonNumber}</th>
                {columns.map(([key]) => (
                  <td key={key}>{formatNumber(row[key])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.lessons.length === 0 ? (
        <PageStatePanel state="empty" title={t`Нет опубликованных занятий`} />
      ) : null}
    </>
  )
}

export function StaffStatisticsReports(props: {
  kind: 'summary' | 'plus-table'
  courseId: string | null
  groupId: string | null
  lessonNumber: number | null
  onCourseChange: (value: string) => void
  onGroupChange: (value: string | null, lesson?: number | null) => void
  onLessonChange: (value: number) => void
}) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  const client = useMemo(
    () =>
      createStatisticsReportsClient(authentication.client.runtime, {
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
  const result = useStatisticsReportQuery(
    client,
    { audience: 'staff', accountId: principal.accountId },
    props.kind,
    props,
  )
  const data = result.data
  const course = data?.courses.find((c) => c.courseId === data.selectedCourseId)
  return (
    <PageLayout title={t`Статистика курса`} width="wide" className="staff-statistics">
      {data ? (
        <div className="flex flex-wrap items-end gap-3">
          <Label className="grid gap-1">
            <Trans>Курс</Trans>
            <select
              className="statistics-select"
              value={data.selectedCourseId ?? ''}
              onChange={(e) => props.onCourseChange(e.target.value)}
            >
              {data.courses.map((c) => (
                <option key={c.courseId} value={c.courseId}>
                  {c.name}
                </option>
              ))}
            </select>
          </Label>
          {props.kind === 'summary' ? (
            <Label className="grid gap-1">
              <Trans>Уровень</Trans>
              <select
                className="statistics-select"
                value={data.selectedGroupId ?? ''}
                onChange={(e) => props.onGroupChange(e.target.value || null)}
              >
                <option value="">{t`Все доступные`}</option>
                {course?.groups.map((g) => (
                  <option key={g.groupId} value={g.groupId}>
                    {g.name}
                  </option>
                ))}
              </select>
            </Label>
          ) : (
            <>
              {'lessonNumbers' in data ? (
                <Label className="grid gap-1">
                  <Trans>Занятие</Trans>
                  <select
                    className="statistics-select"
                    value={data.lessonNumber ?? ''}
                    onChange={(e) => props.onLessonChange(Number(e.target.value))}
                  >
                    {[
                      ...new Set([
                        ...data.lessonNumbers,
                        ...(data.lessonNumber === null ? [] : [data.lessonNumber]),
                      ]),
                    ]
                      .sort((a, b) => a - b)
                      .map((n) => (
                        <option key={n} value={n}>
                          {n}
                        </option>
                      ))}
                  </select>
                </Label>
              ) : null}
              <div className="flex flex-wrap gap-2" aria-label={t`Уровень`}>
                {course?.groups.map((g) => (
                  <Button
                    key={g.groupId}
                    size="sm"
                    variant={g.groupId === data.selectedGroupId ? 'secondary' : 'outline'}
                    aria-pressed={g.groupId === data.selectedGroupId}
                    onClick={() =>
                      props.onGroupChange(
                        g.groupId,
                        'lessonNumber' in data ? data.lessonNumber : undefined,
                      )
                    }
                  >
                    {g.name}
                  </Button>
                ))}
              </div>
            </>
          )}
          <Button
            variant="outline"
            onClick={() => void result.refetch()}
            disabled={result.isFetching}
          >
            <Trans>Обновить статистику</Trans>
          </Button>
        </div>
      ) : null}
      {result.isPending ? (
        <PageStatePanel state="loading" />
      ) : result.error ? (
        <PageStatePanel
          state={
            result.error instanceof ApiResponseError && result.error.status === 403
              ? 'forbidden'
              : 'error'
          }
          actionLabel={t`Повторить`}
          onAction={() => void result.refetch()}
        />
      ) : data ? (
        data.courses.length === 0 ? (
          <PageStatePanel state="empty" title={t`Нет доступных курсов`} />
        ) : 'rows' in data ? (
          <PlusMatrix data={data} />
        ) : (
          <CourseSummary data={data} />
        )
      ) : null}
    </PageLayout>
  )
}
