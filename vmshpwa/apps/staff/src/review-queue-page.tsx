import { useNavigate } from '@tanstack/react-router'
import { useMemo, useState } from 'react'

import {
  PageLayout,
  PageStatePanel,
  createReviewQueueClient,
  useAuthenticatedPrincipal,
  useAuthentication,
  useClaimReviewItemMutation,
  useReviewQueueQuery,
} from '@vmsh/app-shell'
import { ApiResponseError, type ReviewQueueItem as ReviewQueueContractItem } from '@vmsh/contracts'
import { ReviewQueue, type GroupView, type ReviewQueueItem, type ReviewSort } from '@vmsh/product'
import { Alert, AlertContent, AlertDescription, AlertTitle } from '@vmsh/ui'

import { describeReviewError } from './review-errors'

/** Live Phase-6 Staff queue; see development-plan/10-phase-6-review-and-feedback.md. */
export function StaffReviewQueuePage() {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  const navigate = useNavigate()
  const [sort, setSort] = useState<ReviewSort>('waiting')
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
  const queue = useReviewQueueQuery(client, principal)
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
        <ReviewQueue
          items={items}
          onOpen={(id) => void open(id)}
          onSortChange={setSort}
          sort={sort}
        />
      </div>
    )
  }

  return (
    <PageLayout
      description="Работа блокируется за одним учителем; обновление страницы не теряет черновик проверки."
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
