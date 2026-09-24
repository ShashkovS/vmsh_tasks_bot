import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { Link, useNavigate } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useState, type ComponentProps } from 'react'
import { ChevronDown } from 'lucide-react'

import {
  PageLayout,
  PageStatePanel,
  createReviewQueueClient,
  useAuthenticatedPrincipal,
  useAuthentication,
  useClaimReviewItemMutation,
} from '@vmsh/app-shell'
import {
  ApiResponseError,
  reviewQueueQueryKeys,
  type ReviewQueueItem as ReviewQueueContractItem,
} from '@vmsh/contracts'
import { ReviewQueue, type GroupView, type ReviewQueueItem } from '@vmsh/product'
import { Alert, AlertContent, AlertDescription, AlertTitle, Button } from '@vmsh/ui'
import { allReviewItems } from './review-series-model'
import { Route } from './routes/review'
import {
  filterReviewQueue,
  formatReviewWaiting,
  queueOptions,
  reviewQueueCounts,
  sortedReviewProblems,
  workCount,
  type ReviewQueueSearch,
} from './review-queue-model'

import { describeReviewError } from './review-errors'

/** Staff queue: docs/serial-review.md; dev/design-system/05-pages-and-flows.md. */
export function StaffReviewQueuePage() {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  const navigate = useNavigate()
  const search = Route.useSearch()
  const byProblem = search.queueView !== 'works'
  const sort = search.queueTableSort ?? 'waiting'
  const updateSearch = (patch: Partial<ReviewQueueSearch>) =>
    void navigate({
      to: '/review',
      search: (previous) => ({ ...previous, ...patch }),
      resetScroll: false,
    })
  const [now, setNow] = useState(Date.now)
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 60_000)
    return () => window.clearInterval(timer)
  }, [])
  const [openingId, setOpeningId] = useState<string | null>(null)
  const client = useMemo(
    () =>
      createReviewQueueClient(authentication.client.runtime, {
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
  const queue = useQuery({
    queryKey: [...reviewQueueQueryKeys.all(principal), 'all-items'],
    queryFn: async ({ signal }) => ({ items: await allReviewItems(client, signal) }),
    meta: { realtimeResources: ['review-queue'] },
  })
  const claim = useClaimReviewItemMutation(client, principal)

  const open = async (queueId: string) => {
    if (openingId) return
    claim.reset()
    setOpeningId(queueId)
    try {
      await claim.mutateAsync(queueId)
      await navigate({
        to: '/review/$submissionId',
        params: { submissionId: queueId },
        search: true,
      })
    } catch (error) {
      authentication.handleApiError(error)
      setOpeningId(null)
    }
  }

  let content
  if (queue.isPending) {
    content = <PageStatePanel state="loading" />
  } else if (queue.error) {
    content = (
      <PageStatePanel
        actionLabel={t`Повторить`}
        description={describeReviewError(queue.error)}
        onAction={() => void queue.refetch()}
        state={
          queue.error instanceof ApiResponseError && queue.error.status === 403
            ? 'forbidden'
            : 'error'
        }
      />
    )
  } else if (!queue.data?.items.length) {
    content = (
      <PageStatePanel
        description={t`Новые письменные решения появятся здесь автоматически.`}
        state="empty"
        title={t`Все работы проверены`}
      />
    )
  } else {
    const filtered = filterReviewQueue(queue.data.items, search)
    const counts = reviewQueueCounts(filtered)
    const options = queueOptions(queue.data.items, search.queueCourse)
    const items = filtered.map((item) => mapQueueItem(item, openingId, now))
    content = (
      <div className="space-y-3">
        {claim.error ? (
          <Alert tone="danger" role="alert">
            <AlertContent>
              <AlertTitle>
                <Trans>Не удалось открыть работу</Trans>
              </AlertTitle>
              <AlertDescription>{describeReviewError(claim.error)}</AlertDescription>
            </AlertContent>
          </Alert>
        ) : null}
        <dl
          aria-label={t`Сводка очереди`}
          className="grid gap-3 rounded-md border border-border bg-surface p-3 sm:grid-cols-3"
        >
          {[
            [t`Ждут проверки`, counts.total],
            [t`Можно проверить`, counts.available],
            [t`У других преподавателей`, counts.busy],
          ].map(([label, value]) => (
            <div key={label}>
              <dt className="text-small text-muted-foreground">{label}</dt>
              <dd className="font-num text-lg font-semibold">{workCount(Number(value))}</dd>
            </div>
          ))}
        </dl>
        <div className="grid gap-3 sm:grid-cols-2">
          <QueueSelect
            label={t`Курс`}
            value={search.queueCourse ?? ''}
            onChange={(event) => {
              const course = event.target.value || undefined
              const groups = queueOptions(queue.data.items, course).groups
              updateSearch({
                queueCourse: course,
                queueGroup: groups.some((g) => g.id === search.queueGroup)
                  ? search.queueGroup
                  : undefined,
              })
            }}
          >
            <option value="">
              <Trans>Все курсы</Trans>
            </option>
            {search.queueCourse && !options.courses.some((c) => c.id === search.queueCourse) ? (
              <option value={search.queueCourse}>
                <Trans>Выбранный курс — нет работ</Trans>
              </option>
            ) : null}
            {options.courses.map((course) => (
              <option key={course.id} value={course.id}>
                {course.name}
              </option>
            ))}
          </QueueSelect>
          <QueueSelect
            label={t`Группа`}
            value={search.queueGroup ?? ''}
            onChange={(event) => updateSearch({ queueGroup: event.target.value || undefined })}
          >
            <option value="">
              <Trans>Все группы</Trans>
            </option>
            {search.queueGroup && !options.groups.some((g) => g.id === search.queueGroup) ? (
              <option value={search.queueGroup}>
                <Trans>Выбранная группа — нет работ</Trans>
              </option>
            ) : null}
            {options.groups.map((group) => (
              <option key={group.id} value={group.id}>
                {group.name}
              </option>
            ))}
          </QueueSelect>
        </div>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="flex flex-wrap gap-2">
            <Button
              aria-pressed={byProblem}
              variant={byProblem ? 'default' : 'outline'}
              onClick={() => updateSearch({ queueView: 'problems' })}
            >
              <Trans>По задачам</Trans>
            </Button>
            <Button
              aria-pressed={!byProblem}
              variant={byProblem ? 'outline' : 'default'}
              onClick={() => updateSearch({ queueView: 'works' })}
            >
              <Trans>Все работы</Trans>
            </Button>
          </div>
          {byProblem ? (
            <QueueSelect
              label={t`Порядок задач`}
              value={search.queueSort ?? 'waiting'}
              onChange={(event) =>
                updateSearch({ queueSort: event.target.value === 'count' ? 'count' : 'waiting' })
              }
            >
              <option value="waiting">
                <Trans>Дольше ждут</Trans>
              </option>
              <option value="count">
                <Trans>Больше работ</Trans>
              </option>
            </QueueSelect>
          ) : null}
        </div>
        {!filtered.length ? (
          <PageStatePanel
            state="empty"
            title={t`По выбранным фильтрам работ нет`}
            actionLabel={t`Сбросить фильтры`}
            onAction={() => updateSearch({ queueCourse: undefined, queueGroup: undefined })}
          />
        ) : byProblem ? (
          <div className="space-y-2">
            {sortedReviewProblems(filtered, search.queueSort).map(
              ({ problem, items: grouped, oldest }) => {
                const { total, available, busy } = reviewQueueCounts(grouped)
                return (
                  <article
                    aria-label={`${problem.problemNumber} · ${problem.problemTitle}`}
                    key={problem.problemId}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border bg-surface p-3"
                  >
                    <div className="min-w-0 flex-1 basis-64 break-words">
                      <div className="font-semibold">
                        {problem.problemNumber} · {problem.problemTitle}
                      </div>
                      <div className="text-caption text-muted-foreground">
                        {problem.courseName} · {problem.groupName}
                      </div>
                      <p className="mt-2 font-medium">
                        <Trans>Ждут проверки:</Trans> {workCount(total)}
                      </p>
                      {busy > 0 ? (
                        <p className="text-small text-muted-foreground">
                          <Trans>
                            Можно проверить: {available} · У других преподавателей: {busy}
                          </Trans>
                        </p>
                      ) : null}
                      <p className="text-small text-muted-foreground">
                        <Trans>Самая давняя работа ждёт </Trans>
                        {formatReviewWaiting((now - Date.parse(oldest)) / 60_000)}
                      </p>
                      {!available ? (
                        <p className="text-small text-muted-foreground">
                          <Trans>Все работы уже взяты другими преподавателями</Trans>
                        </p>
                      ) : null}
                    </div>
                    <Button
                      disabled={!available}
                      className="aria-disabled:opacity-50"
                      render={
                        <Link
                          to="/review/series/$problemId"
                          search={true}
                          params={{ problemId: problem.problemId }}
                        />
                      }
                    >
                      <Trans>Проверять подряд</Trans>
                    </Button>
                  </article>
                )
              },
            )}
          </div>
        ) : (
          <ReviewQueue
            items={items}
            onOpen={(id) => void open(id)}
            onSortChange={(queueTableSort) => updateSearch({ queueTableSort })}
            showSummary={false}
            sort={sort}
          />
        )}
      </div>
    )
  }

  return (
    <PageLayout
      description={t`Выберите задачу для серийной проверки или откройте отдельную работу.`}
      eyebrow={t`Письменные задачи`}
      title={t`Очередь проверки`}
      width="wide"
    >
      {content}
    </PageLayout>
  )
}

function mapQueueItem(
  item: ReviewQueueContractItem,
  openingId: string | null,
  now: number,
): ReviewQueueItem {
  const first = item.branches[0]!
  const waitingMinutes = Math.max(
    0,
    Math.floor((now - new Date(item.submittedAt).getTime()) / 60_000),
  )
  const group: GroupView = {
    id: first.groupId ?? first.groupShortCode,
    courseId: first.courseId ?? 'legacy-course',
    code: first.groupShortCode,
    name: first.groupName,
    colorIndex: colorIndex(first.groupColorKey),
  }
  return {
    id: item.queueId,
    taskNumber: first.problemNumber,
    taskTitle:
      item.branches.length === 1
        ? first.problemTitle
        : t`${first.problemTitle} · ${item.branches.length} синонимичные ветки`,
    level: group,
    studentName: item.student.displayName,
    groupName:
      item.branches.length === 1
        ? first.groupName
        : [...new Set(item.branches.map((branch) => branch.groupName))].join(', '),
    waitingLabel: formatReviewWaiting(waitingMinutes),
    waitingMinutes,
    ...(openingId === item.queueId
      ? { busyBy: t`открываем…` }
      : item.lock && !item.lock.isOwnedByCurrentStaff
        ? { busyBy: item.lock.teacher.displayName }
        : {}),
  }
}

function colorIndex(colorKey: string | null): 0 | 1 | 2 | 3 | 4 {
  const match = /^level-([1-4])$/.exec(colorKey ?? '')
  return match ? (Number(match[1]) as 1 | 2 | 3 | 4) : 0
}

/** Native keyboard behavior with consistent WebKit sizing; docs/serial-review.md. */
function QueueSelect({ label, children, ...props }: ComponentProps<'select'> & { label: string }) {
  return (
    <label className="flex min-w-0 flex-col gap-1 text-small">
      <span>{label}</span>
      <span className="relative block">
        <select
          {...props}
          className="min-h-10 w-full min-w-0 appearance-none rounded-md border border-border bg-surface py-2 pr-9 pl-3 text-small text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
        >
          {children}
        </select>
        <ChevronDown
          aria-hidden="true"
          className="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-muted-foreground"
        />
      </span>
    </label>
  )
}
