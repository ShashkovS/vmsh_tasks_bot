import { Link, useNavigate } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

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
import { ReviewQueue, type GroupView, type ReviewQueueItem, type ReviewSort } from '@vmsh/product'
import { Alert, AlertContent, AlertDescription, AlertTitle, Button } from '@vmsh/ui'
import { allReviewItems, reviewProblemGroups } from './review-series-model'

import { describeReviewError } from './review-errors'

/** Live Phase-6 Staff queue; see development-plan/10-phase-6-review-and-feedback.md. */
export function StaffReviewQueuePage() {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  const navigate = useNavigate()
  const [sort, setSort] = useState<ReviewSort>('waiting')
  const [byProblem, setByProblem] = useState(true)
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
      await navigate({ to: '/review/$submissionId', params: { submissionId: queueId } })
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
        actionLabel="Повторить"
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
        description="Новые письменные решения появятся здесь автоматически."
        state="empty"
        title="Все работы проверены"
      />
    )
  } else {
    const items = queue.data.items.map((item) => mapQueueItem(item, openingId))
    content = (
      <div className="space-y-3">
        {claim.error ? (
          <Alert tone="danger" role="alert">
            <AlertContent>
              <AlertTitle>Не удалось открыть работу</AlertTitle>
              <AlertDescription>{describeReviewError(claim.error)}</AlertDescription>
            </AlertContent>
          </Alert>
        ) : null}
        <div className="flex gap-2">
          <Button variant={byProblem ? 'default' : 'outline'} onClick={() => setByProblem(true)}>
            По задачам
          </Button>
          <Button variant={byProblem ? 'outline' : 'default'} onClick={() => setByProblem(false)}>
            Все работы
          </Button>
        </div>
        {byProblem ? (
          <div className="space-y-2">
            {reviewProblemGroups(queue.data.items).map(({ problem, items: grouped, oldest }) => {
              const available = grouped.filter(
                (item) => !item.lock || item.lock.isOwnedByCurrentStaff,
              ).length
              return (
                <div
                  key={problem.problemId}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border bg-surface p-3"
                >
                  <div>
                    <div className="font-semibold">
                      {problem.problemNumber} · {problem.problemTitle}
                    </div>
                    <div className="text-caption text-muted-foreground">
                      {problem.courseName} · {problem.groupName} · {available} свободно из{' '}
                      {grouped.length} · ждёт{' '}
                      {formatWaiting(
                        Math.max(
                          0,
                          Math.floor((queue.dataUpdatedAt - Date.parse(oldest)) / 60_000),
                        ),
                      )}
                    </div>
                  </div>
                  <Button
                    disabled={!available}
                    render={
                      <Link
                        to="/review/series/$problemId"
                        params={{ problemId: problem.problemId }}
                      />
                    }
                  >
                    Проверять подряд
                  </Button>
                </div>
              )
            })}
          </div>
        ) : (
          <ReviewQueue
            items={items}
            onOpen={(id) => void open(id)}
            onSortChange={setSort}
            sort={sort}
          />
        )}
      </div>
    )
  }

  return (
    <PageLayout
      description="Выберите задачу для серийной проверки. Сверху — задачи, по которым дольше всего ждут проверки."
      eyebrow="Письменные задачи"
      title="Очередь проверки"
      width="wide"
    >
      {content}
    </PageLayout>
  )
}

function mapQueueItem(item: ReviewQueueContractItem, openingId: string | null): ReviewQueueItem {
  const first = item.branches[0]!
  const waitingMinutes = Math.max(
    0,
    Math.floor((Date.now() - new Date(item.submittedAt).getTime()) / 60_000),
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
        : `${first.problemTitle} · ${item.branches.length} синонимичные ветки`,
    level: group,
    studentName: item.student.displayName,
    groupName:
      item.branches.length === 1
        ? first.groupName
        : [...new Set(item.branches.map((branch) => branch.groupName))].join(', '),
    waitingLabel: formatWaiting(waitingMinutes),
    waitingMinutes,
    ...(openingId === item.queueId
      ? { busyBy: 'открываем…' }
      : item.lock && !item.lock.isOwnedByCurrentStaff
        ? { busyBy: item.lock.teacher.displayName }
        : {}),
  }
}

function colorIndex(colorKey: string | null): 0 | 1 | 2 | 3 | 4 {
  const match = /^level-([1-4])$/.exec(colorKey ?? '')
  return match ? (Number(match[1]) as 1 | 2 | 3 | 4) : 0
}

function formatWaiting(minutes: number): string {
  if (minutes < 60) return `${minutes} мин`
  const hours = Math.floor(minutes / 60)
  const remainder = minutes % 60
  return remainder ? `${hours} ч ${remainder} мин` : `${hours} ч`
}
