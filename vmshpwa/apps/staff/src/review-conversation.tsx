import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { useInfiniteQuery } from '@tanstack/react-query'
import type { ReviewQueueClient } from '@vmsh/app-shell'
import { Button } from '@vmsh/ui'
import { HistoryEvents } from './student-results-history'

// docs/review-history.md: the original authorized review anchors every history/media read.
export function ReviewConversation({
  client,
  reviewId,
  accountId,
  namespace,
  threadVersion,
}: {
  client: Pick<ReviewQueueClient, 'conversation'>
  reviewId: string
  accountId: string
  namespace: string
  threadVersion: number
}) {
  const query = useInfiniteQuery({
    queryKey: ['review-conversation', namespace, accountId, reviewId, threadVersion],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam, signal }) => client.conversation(reviewId, pageParam, { signal }),
    getNextPageParam: (last) => last.nextCursor ?? undefined,
  })
  const events = query.data?.pages.flatMap((page) => page.events) ?? []
  return (
    <details open>
      <summary>
        <Trans>История переписки и проверок</Trans>
      </summary>
      <section aria-label={t`История переписки и проверок`} className="space-y-3 pt-3">
        {query.isPending && (
          <p role="status">
            <Trans>Загружаем историю…</Trans>
          </p>
        )}
        {query.isError && (
          <p role="alert">
            <Trans>Не удалось загрузить историю. </Trans>
            <Button
              variant="outline"
              onClick={() =>
                void (query.isFetchNextPageError ? query.fetchNextPage() : query.refetch())
              }
            >
              <Trans>Повторить</Trans>
            </Button>
          </p>
        )}
        {!query.isPending && !query.isError && !events.length && (
          <p>
            <Trans>Сохранённых событий нет.</Trans>
          </p>
        )}
        <HistoryEvents events={events} openReviews={false} />
        {query.hasNextPage && (
          <Button
            variant="outline"
            disabled={query.isFetchingNextPage}
            onClick={() => void query.fetchNextPage()}
          >
            <Trans>
              Ещё 50 событий ({events.length} из {query.data?.pages[0]?.total})
            </Trans>
          </Button>
        )}
      </section>
    </details>
  )
}
