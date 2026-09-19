import { useMemo, useState } from 'react'

import {
  PageLayout,
  PageStatePanel,
  createReviewQueueClient,
  useAuthenticatedPrincipal,
  useAuthentication,
  useInfiniteReviewReactionInboxQuery,
  useCorrectWrittenReviewMutation,
} from '@vmsh/app-shell'
import {
  ApiResponseError,
  createBrowserStorageNamespace,
  type ReviewReactionId,
  type ReviewReactionInboxItem,
} from '@vmsh/contracts'
import {
  ReviewFeedbackForm,
  ReviewReactionInbox,
  fullVerdictScale,
  writtenReviewVerdict,
  type ReviewFeedbackDraft,
  type ReviewFeedbackResult,
  type ReviewReactionInboxKind,
} from '@vmsh/product'
import {
  Alert,
  AlertContent,
  AlertDescription,
  AlertTitle,
  Button,
  Card,
  CardContent,
} from '@vmsh/ui'

import { describeReviewError } from './review-errors'

/** Admin-only oversight of current Student disagreements and Teacher flags. */
export function StaffReviewReactionInboxPage() {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  const [kind, setKind] = useState<ReviewReactionInboxKind>('all')
  const [reactionId, setReactionId] = useState<ReviewReactionId | null>(null)
  const [rechecking, setRechecking] = useState<ReviewReactionInboxItem | null>(null)
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
          onRecheck={(item) =>
            setRechecking((current) => (current?.reviewId === item.reviewId ? null : item))
          }
          reactionId={reactionId}
          recheckingReviewId={rechecking?.reviewId ?? null}
        />
        {rechecking ? (
          <CorrectionPanel
            client={client}
            item={rechecking}
            onClose={() => setRechecking(null)}
            principal={principal}
          />
        ) : null}
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

const verdictToWire = {
  rejected: 11,
  'minus-dot': 12,
  'minus-plus': 13,
  half: 14,
  'plus-minus': 15,
  'plus-dot': 16,
  plus: 17,
} as const

interface StoredCorrectionDraft {
  idempotencyKey: string
  draft: ReviewFeedbackDraft
}

function CorrectionPanel({
  client,
  item,
  onClose,
  principal,
}: {
  client: ReturnType<typeof createReviewQueueClient>
  item: ReviewReactionInboxItem
  onClose: () => void
  principal: ReturnType<typeof useAuthenticatedPrincipal>
}) {
  const authentication = useAuthentication()
  const namespace = createBrowserStorageNamespace(authentication.client.runtime)
  const storageKey = `${namespace}:review-correction:${principal.accountId}:${item.reviewId}`
  const initial = readCorrectionDraft(storageKey, item)
  const [stored, setStored] = useState(initial)
  const correction = useCorrectWrittenReviewMutation(client, principal, item.reviewId)

  const saveDraft = (draft: ReviewFeedbackDraft) => {
    const next = { ...stored, draft }
    setStored(next)
    window.localStorage.setItem(storageKey, JSON.stringify(next))
  }
  const submit = async (result: ReviewFeedbackResult) => {
    const verdict = verdictToWire[result.verdict.value as keyof typeof verdictToWire]
    if (!verdict) return
    try {
      await correction.mutateAsync({
        schemaVersion: 1,
        idempotencyKey: stored.idempotencyKey,
        verdict,
        comment: result.comment || null,
        confirmWithoutComment: verdict < 16 && result.comment === '',
      })
      window.localStorage.removeItem(storageKey)
      onClose()
    } catch (error) {
      authentication.handleApiError(error)
    }
  }

  return (
    <Card aria-label={`Перепроверка: ${item.student.displayName}`}>
      <CardContent className="space-y-3 pt-4">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <p className="text-small font-semibold text-foreground">
              Перепроверка · {item.student.displayName}
            </p>
            <p className="text-caption text-muted-foreground">
              {item.problem.problemNumber} · {item.problem.problemTitle} · прежний вердикт:{' '}
              {writtenReviewVerdict(item.verdict).label}
            </p>
          </div>
          <Button onClick={onClose} size="xs" variant="ghost">
            Закрыть
          </Button>
        </div>
        <Alert tone="info">
          <AlertContent>
            <AlertTitle>Исходная проверка останется в истории</AlertTitle>
            <AlertDescription>
              Новый вердикт станет текущим. Фото, переписка, прежний комментарий и реакция не
              изменяются.
            </AlertDescription>
          </AlertContent>
        </Alert>
        <section aria-label="Исходная работа ученика" className="space-y-2">
          <h3 className="text-small font-semibold text-foreground">Работа ученика</h3>
          {item.evidenceEntries.map((entry) => (
            <article className="space-y-2 rounded-md border border-border p-2" key={entry.entryId}>
              {entry.text ? (
                <p className="whitespace-pre-wrap text-small text-foreground">{entry.text}</p>
              ) : null}
              {entry.attachments.length > 0 ? (
                <div className="grid gap-2 sm:grid-cols-2">
                  {entry.attachments.map((attachment) => (
                    <img
                      alt={`Страница ${attachment.ordinal + 1} решения ученика`}
                      className="max-h-80 w-full rounded-md border border-border bg-surface object-contain"
                      key={attachment.attachmentId}
                      loading="lazy"
                      src={`${authentication.client.runtime.apiBase}/thread-entries/${encodeURIComponent(entry.entryId)}/attachments/${encodeURIComponent(attachment.attachmentId)}/media`}
                    />
                  ))}
                </div>
              ) : null}
            </article>
          ))}
        </section>
        {correction.error ? (
          <Alert role="alert" tone="danger">
            <AlertContent>
              <AlertTitle>Не удалось сохранить перепроверку</AlertTitle>
              <AlertDescription>{describeReviewError(correction.error)}</AlertDescription>
            </AlertContent>
          </Alert>
        ) : null}
        <ReviewFeedbackForm
          disabled={correction.isPending}
          initialDraft={stored.draft}
          key={item.reviewId}
          onDraftChange={saveDraft}
          onSubmit={(result) => void submit(result)}
          showInternalReaction={false}
          verdicts={fullVerdictScale}
        />
      </CardContent>
    </Card>
  )
}

function readCorrectionDraft(
  storageKey: string,
  item: ReviewReactionInboxItem,
): StoredCorrectionDraft {
  try {
    const raw = window.localStorage.getItem(storageKey)
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<StoredCorrectionDraft>
      if (typeof parsed.idempotencyKey === 'string' && parsed.draft) {
        return parsed as StoredCorrectionDraft
      }
    }
  } catch {
    // A blocked or corrupt localStorage must not prevent the admin from correcting.
  }
  return {
    idempotencyKey: crypto.randomUUID(),
    draft: {
      verdictValue: writtenReviewVerdict(item.verdict).value,
      comment: item.comment ?? '',
      reactionId: null,
    },
  }
}
