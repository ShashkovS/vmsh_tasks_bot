import { Link } from '@tanstack/react-router'
import { useMemo } from 'react'

import {
  PageLayout,
  PageStatePanel,
  createNewsClient,
  useAuthenticatedPrincipal,
  useAuthentication,
  useNewsFeedQuery,
  useNewsPostQuery,
} from '@vmsh/app-shell'
import { ApiResponseError } from '@vmsh/contracts'
import { createOfflineNewsClient, useOfflineDatabase } from '@vmsh/offline'
import { TelegramRichPost, toTelegramPostView } from '@vmsh/product'
import { Button, buttonVariants } from '@vmsh/ui'

function formatMoment(value: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'long',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Europe/Moscow',
  }).format(new Date(value))
}

function useFamilyNewsClient() {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'family') throw new Error('Family news requires Family auth')
  const database = useOfflineDatabase()
  return useMemo(() => {
    const online = createNewsClient(authentication.client.runtime, 'family', {
      refreshSession: async () => {
        try {
          return await authentication.refresh()
        } catch (error) {
          authentication.handleApiError(error)
          throw error
        }
      },
    })
    return createOfflineNewsClient(online, database, principal.accountId)
  }, [authentication, database, principal.accountId])
}

/** Production Family read-only news feed. */
export function FamilyNewsFeedPage() {
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'family') throw new Error('Family news requires Family auth')
  const client = useFamilyNewsClient()
  const query = useNewsFeedQuery(client, {
    audience: 'family',
    accountId: principal.accountId,
  })
  const items = query.data?.pages.flatMap((page) => page.items) ?? []

  let content
  if (query.isPending) {
    content = <PageStatePanel state="loading" />
  } else if (query.error) {
    content = (
      <PageStatePanel
        actionLabel="Повторить"
        onAction={() => void query.refetch()}
        state={
          query.error instanceof ApiResponseError && query.error.status === 403
            ? 'forbidden'
            : 'error'
        }
      />
    )
  } else if (items.length === 0) {
    content = <PageStatePanel state="empty" />
  } else {
    content = (
      <div className="space-y-4">
        {items.map((item) => (
          <div className="space-y-2" key={item.postId}>
            <TelegramRichPost post={toTelegramPostView(item, formatMoment)} variant="card" />
            <Link
              className={buttonVariants({ size: 'sm', variant: 'ghost' })}
              params={{ postId: item.postId }}
              to="/news/$postId"
            >
              Открыть публикацию
            </Link>
          </div>
        ))}
        {query.hasNextPage ? (
          <Button
            disabled={query.isFetchingNextPage}
            onClick={() => void query.fetchNextPage()}
            variant="outline"
          >
            {query.isFetchingNextPage ? 'Загружаем…' : 'Показать более ранние'}
          </Button>
        ) : null}
      </div>
    )
  }

  return (
    <PageLayout
      description="Публикации курсов и групп, доступных вашим детям."
      title="Новости"
      width="reading"
    >
      {content}
    </PageLayout>
  )
}

export function FamilyNewsPostPage({ postId }: { postId: string }) {
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'family') throw new Error('Family news requires Family auth')
  const client = useFamilyNewsClient()
  const query = useNewsPostQuery(
    client,
    { audience: 'family', accountId: principal.accountId },
    postId,
  )

  return (
    <PageLayout title="Публикация" width="reading">
      {query.isPending ? <PageStatePanel state="loading" /> : null}
      {query.error ? (
        <PageStatePanel
          actionLabel="Повторить"
          onAction={() => void query.refetch()}
          state={
            query.error instanceof ApiResponseError && query.error.status === 403
              ? 'forbidden'
              : 'error'
          }
        />
      ) : null}
      {query.data ? (
        <TelegramRichPost post={toTelegramPostView(query.data.item, formatMoment)} />
      ) : null}
    </PageLayout>
  )
}
