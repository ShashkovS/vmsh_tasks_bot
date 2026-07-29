import { useMemo, useState } from 'react'

import {
  PageLayout,
  PageStatePanel,
  createReviewQueueClient,
  useAuthenticatedPrincipal,
  useAuthentication,
  useInfiniteReviewReactionInboxQuery,
} from '@vmsh/app-shell'
import { ApiResponseError, type ReviewReactionId } from '@vmsh/contracts'
import { ReviewReactionInbox, type ReviewReactionInboxKind } from '@vmsh/product'
import { Button } from '@vmsh/ui'

import { describeReviewError } from './review-errors'

/** Admin-only oversight of current Student disagreements and Teacher flags. */
export function StaffReviewReactionInboxPage() {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  const [kind, setKind] = useState<ReviewReactionInboxKind>('all')
  const [reactionId, setReactionId] = useState<ReviewReactionId | null>(null)
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
  const inbox = useInfiniteReviewReactionInboxQuery(client, principal, {
    kind,
    ...(reactionId === null ? {} : { reactionId }),
  })

  const changeKind = (nextKind: ReviewReactionInboxKind) => {
    setKind(nextKind)
    setReactionId((current) => {
      if (current === null || nextKind === 'all') return current
      if (nextKind === 'student') return current < 100 ? current : null
      return current >= 100 ? current : null
    })
  }

  let content
  if (inbox.isPending) {
    content = <PageStatePanel state="loading" />
  } else if (inbox.error) {
    content = (
      <PageStatePanel
        actionLabel="Повторить"
        description={describeReviewError(inbox.error)}
        onAction={() => void inbox.refetch()}
        state={
          inbox.error instanceof ApiResponseError && inbox.error.status === 403
            ? 'forbidden'
            : 'error'
        }
      />
    )
  } else {
    const items = inbox.data?.pages.flatMap((page) => page.items) ?? []
    content = (
      <div className="space-y-3">
        <ReviewReactionInbox
          items={items}
          kind={kind}
          onKindChange={changeKind}
          onReactionIdChange={setReactionId}
          reactionId={reactionId}
        />
        {inbox.hasNextPage ? (
          <Button
            disabled={inbox.isFetchingNextPage}
            onClick={() => void inbox.fetchNextPage()}
            size="sm"
            variant="outline"
          >
            {inbox.isFetchingNextPage ? 'Загружаем…' : 'Показать ещё'}
          </Button>
        ) : null}
      </div>
    )
  }

  return (
    <PageLayout
      description="Реакции помогают заметить спорную проверку или подозрение преподавателя, но сами не меняют результат."
      eyebrow="Контроль проверки"
      title="Реакции и разногласия"
      width="wide"
    >
      {content}
    </PageLayout>
  )
}
