import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { useInfiniteQuery } from '@tanstack/react-query'
import { useAuthenticatedPrincipal } from '@vmsh/app-shell'
import { aiReviewSuggestionsSchema, type ReviewWorkspaceEvidence } from '@vmsh/contracts'
import type { ReviewFeedbackDraft } from '@vmsh/product'
import { Button } from '@vmsh/ui'
import { aiEvidenceKey, applyAiSuggestion } from './ai-review-model'
import { AiReviewSuggestionsView } from './ai-review-suggestions-view'
import { useAiReviewRequest } from './ai-review-client'

/** Independent optional query; docs/ai-review-assistant.md, all Staff review modes. */
export function AiReviewPanel({
  workspace,
  queueId,
  caseId,
  draft,
  onDraftChange,
  disabled,
  active = true,
}: {
  workspace: ReviewWorkspaceEvidence
  queueId?: string
  caseId?: string
  draft: ReviewFeedbackDraft
  onDraftChange: (draft: ReviewFeedbackDraft) => void
  disabled?: boolean
  active?: boolean
}) {
  const principal = useAuthenticatedPrincipal()
  const request = useAiReviewRequest()
  const evidenceKey = aiEvidenceKey(workspace)
  const query = useInfiniteQuery({
    queryKey: ['ai-review-suggestions', principal.accountId, caseId ?? queueId, evidenceKey],
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam, signal }) => {
      const search = new URLSearchParams(caseId ? { caseId } : { queueId: queueId! })
      if (pageParam) search.set('cursor', pageParam)
      return aiReviewSuggestionsSchema.parse(
        await request(`/review/ai-suggestions?${search}`, { signal }),
      )
    },
    getNextPageParam: (last) => last.nextCursor,
    enabled: Boolean(caseId || queueId),
    retry: false,
    refetchInterval: active ? 30_000 : false,
    refetchOnWindowFocus: active,
    meta: { realtimeResources: [] },
  })
  const first = query.data?.pages[0]
  const items =
    query.data?.pages.flatMap((p) =>
      p.items.map((item) => ({
        ...item,
        isCurrent: item.isCurrent && item.snapshot === first?.snapshot,
      })),
    ) ?? []
  if (query.isError && !first)
    return (
      <div className="text-small text-muted-foreground">
        <Trans>Предложения ИИ временно недоступны.</Trans>{' '}
        <Button size="sm" variant="ghost" onClick={() => void query.refetch()}>
          <Trans>Повторить</Trans>
        </Button>
      </div>
    )
  if (items.length === 0) return null
  const matches = first?.pending && first.evidenceKey === evidenceKey
  return (
    <AiReviewSuggestionsView
      items={items}
      currentWork={Boolean(matches && !query.isError)}
      disabled={Boolean(disabled)}
      onApply={(item, field) => onDraftChange(applyAiSuggestion(draft, item, field))}
      more={
        query.hasNextPage ? (
          <Button
            variant="ghost"
            disabled={query.isFetchingNextPage}
            onClick={() => void query.fetchNextPage()}
          >{t`Ещё предложения`}</Button>
        ) : null
      }
    />
  )
}
