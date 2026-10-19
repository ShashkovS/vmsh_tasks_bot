import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import {
  useAuthentication,
  type ReviewQueueClient,
  type WrittenMaterialReassignmentClient,
} from '@vmsh/app-shell'
import {
  ApiResponseError,
  type ReviewSheetCollection,
  type ReviewSheetDetail,
  type ReviewSheetConversation,
  type BrowserStorageNamespace,
  writtenTeacherReactionIdSchema,
} from '@vmsh/contracts'
import {
  ReviewFeedbackForm,
  ThreePaneReview,
  binaryVerdictScale,
  ternaryVerdictScale,
  fullVerdictScale,
  writtenReviewVerdict,
  type ReviewFeedbackDraft,
  type ReviewFeedbackResult,
} from '@vmsh/product'
import { Button } from '@vmsh/ui'
import {
  createEmptyReviewDraft,
  createReviewEvidenceFingerprint,
  reviewDraftSchema,
  writeReviewDraft,
  clearReviewDraft,
  type ReviewDraft,
} from './review-draft'
import { HistoryEvents } from './student-results-history'
import { ReviewEvidenceEntry } from './review-workspace-page'
import { describeReviewError } from './review-errors'
import { rememberCompletedReview } from './last-completed-review'
import { ReviewTransfer } from './review-transfer'
import { AiReviewPanel } from './ai-review-panel'

const scales = {
  verdict_plus_minus: binaryVerdictScale,
  verdict_plus_minus_half: ternaryVerdictScale,
  verdict_plus_steps: fullVerdictScale,
}
const wireVerdicts = {
  rejected: 11,
  'minus-dot': 12,
  'minus-plus': 13,
  half: 14,
  'plus-minus': 15,
  'plus-dot': 16,
  plus: 17,
} as const
type SheetItem = ReviewSheetCollection['tasks'][number]['cases'][number]

/** Per-case drafts and local refresh; docs/review-sheet.md, shared ReviewFeedbackForm. */
export function ReviewSheetCard({
  item,
  client,
  mediaClient,
  accountId,
  namespace,
  active,
  onActivate,
  onDeactivate,
}: {
  item: SheetItem
  client: ReviewQueueClient
  mediaClient: WrittenMaterialReassignmentClient
  accountId: string
  namespace: BrowserStorageNamespace
  active: boolean
  onActivate: () => void
  onDeactivate: () => void
}) {
  const element = useRef<HTMLElement>(null)
  const [near, setNear] = useState(typeof IntersectionObserver === 'undefined')
  useEffect(() => {
    if (near || !element.current) return
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setNear(true)
          observer.disconnect()
        }
      },
      { rootMargin: '600px' },
    )
    observer.observe(element.current)
    return () => observer.disconnect()
  }, [near])
  const query = useQuery({
    queryKey: [namespace, accountId, 'review-sheet-case', item.caseId],
    queryFn: ({ signal }) => client.sheetDetail(item.caseId, { signal }),
    enabled: near,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    meta: { realtimeResources: [] },
  })
  return (
    <article
      ref={element}
      aria-label={t`Проверка работы: ${item.studentName}`}
      onFocusCapture={onActivate}
      onPointerDownCapture={onActivate}
      onBlurCapture={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) onDeactivate()
      }}
      className="min-h-32 space-y-3 rounded-lg border border-border bg-surface p-4 focus-visible:outline-2 focus-visible:outline-focus-ring"
    >
      <h3 className="font-semibold">{item.studentName}</h3>
      {!near || query.isPending ? (
        <p role="status">
          <Trans>Загружаем работу…</Trans>
        </p>
      ) : query.error ? (
        <>
          <p role="alert">{describeReviewError(query.error)}</p>
          <Button variant="outline" onClick={() => void query.refetch()}>
            <Trans>Повторить</Trans>
          </Button>
        </>
      ) : query.data ? (
        <LoadedSheetCard
          client={client}
          mediaClient={mediaClient}
          detail={query.data}
          active={active}
          accountId={accountId}
          namespace={namespace}
          onRefresh={async () => {
            const result = await query.refetch()
            if (result.error) throw result.error
            return result.data!
          }}
        />
      ) : null}
    </article>
  )
}

function restoreDraft(key: string, detail: ReviewSheetDetail) {
  try {
    const parsed = reviewDraftSchema.safeParse(
      JSON.parse(window.localStorage.getItem(key) ?? 'null'),
    )
    if (parsed.success && parsed.data.logicalCaseId === detail.caseId) return parsed.data
  } catch {
    /* A denied storage is reported after the first attempted save. */
  }
  return {
    ...createEmptyReviewDraft(detail.caseId, createReviewEvidenceFingerprint(detail.workspace)),
    annotations: detail.annotations,
  }
}

function LoadedSheetCard({
  client,
  mediaClient,
  detail: initialDetail,
  active,
  accountId,
  namespace,
  onRefresh,
}: {
  client: ReviewQueueClient
  mediaClient: WrittenMaterialReassignmentClient
  detail: ReviewSheetDetail
  active: boolean
  accountId: string
  namespace: BrowserStorageNamespace
  onRefresh: () => Promise<ReviewSheetDetail>
}) {
  const authentication = useAuthentication()
  const queryClient = useQueryClient()
  // Only an explicit card refresh advances its CAS snapshot (docs/review-sheet.md).
  const [detail, setDetail] = useState(initialDetail)
  const storageKey = `${namespace}:review-sheet-draft:${accountId}:${detail.caseId}`
  const [draft, setDraft] = useState(() => restoreDraft(storageKey, detail))
  const [busy, setBusy] = useState(false)
  const submitting = useRef(false)
  const [error, setError] = useState<string | null>(null)
  const [changed, setChanged] = useState(
    draft.evidenceFingerprint !== createReviewEvidenceFingerprint(detail.workspace),
  )
  const [refreshFailed, setRefreshFailed] = useState(false)
  const [storageAvailable, setStorageAvailable] = useState(true)
  const [finished, setFinished] = useState(false)
  const [movedTo, setMovedTo] = useState<string | null>(null)
  const [abandoned, setAbandoned] = useState(false)
  const [formVersion, setFormVersion] = useState(0)
  const conversation = useInfiniteQuery({
    queryKey: [namespace, accountId, 'review-sheet-conversation', detail.caseId, detail.snapshot],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam, signal }) =>
      client.sheetConversation(detail.caseId, pageParam, { signal }),
    getNextPageParam: (page) => page.nextCursor ?? undefined,
    refetchOnWindowFocus: false,
    meta: { realtimeResources: [] },
  })
  const { hasNextPage, isFetchingNextPage, isFetchNextPageError, fetchNextPage } = conversation
  useEffect(() => {
    if (hasNextPage && !isFetchingNextPage && !isFetchNextPageError) void fetchNextPage()
  }, [hasNextPage, isFetchingNextPage, isFetchNextPageError, fetchNextPage])
  // Join by public entry ID, including evidence while history pages load (review-sheet.md).
  const evidence = new Map(
    detail.workspace.evidenceBranches.flatMap((branch) =>
      (branch.thread?.timelineEntries ?? []).map((entry) => [entry.entryId, entry] as const),
    ),
  )
  const events = conversation.data?.pages.flatMap((page) => page.events) ?? []
  const loadedEntryIds = new Set(events.map((event) => event.entryId))
  const messages: ReviewSheetConversation['events'] = [
    ...events,
    ...detail.workspace.evidenceBranches.flatMap((branch) => {
      const origin = detail.workspace.branches.find((item) => item.queueId === branch.queueId)
      return (branch.thread?.timelineEntries ?? [])
        .filter((entry) => !loadedEntryIds.has(entry.entryId))
        .map((entry) => ({
          id: `evidence:${entry.entryId}`,
          entryId: entry.entryId,
          kind: 'entry' as const,
          at: entry.submittedAt,
          author: detail.workspace.student.displayName,
          authorKind: entry.authorKind,
          source: 'pwa',
          text: entry.text,
          pasteEstimate: entry.pasteEstimate,
          attachments: [],
          problemNumber: origin?.problemNumber ?? '',
          verdict: null,
          symbol: '',
          revisionId: null,
          reviewId: null,
          internal: false as const,
          action: null,
          transfer: null,
          checkStatus: null,
        }))
    }),
  ]
    .map((event) => ({ ...event, id: event.entryId ? `sheet-entry:${event.entryId}` : event.id }))
    .sort((left, right) => Date.parse(left.at) - Date.parse(right.at))
  const attachmentIds = new Set(
    detail.workspace.evidenceBranches.flatMap(
      (branch) =>
        branch.thread?.entries.flatMap((entry) =>
          entry.attachments.map((photo) => photo.attachmentId),
        ) ?? [],
    ),
  )
  const incompatible = draft.annotations.filter(
    (annotation) => !attachmentIds.has(annotation.attachmentId),
  )
  const store = (next: ReviewDraft) => {
    setDraft(next)
    setStorageAvailable(writeReviewDraft(window.localStorage, storageKey, next))
  }
  const edit = (next: ReviewFeedbackDraft) =>
    store({
      ...draft,
      ...next,
      reactionId:
        next.reactionId === null ? null : writtenTeacherReactionIdSchema.parse(next.reactionId),
      idempotencyKey: `sheet-${crypto.randomUUID()}`,
      updatedAt: new Date().toISOString(),
    })
  const annotate = (attachmentId: string, annotation: ReviewDraft['annotations'][number] | null) =>
    store({
      ...draft,
      annotations: [
        ...draft.annotations.filter((item) => item.attachmentId !== attachmentId),
        ...(annotation ? [annotation] : []),
      ],
      idempotencyKey: `sheet-${crypto.randomUUID()}`,
      updatedAt: new Date().toISOString(),
    })
  const refresh = async () => {
    setRefreshFailed(false)
    try {
      setDetail(await onRefresh())
    } catch (reason) {
      setRefreshFailed(true)
      setError(describeReviewError(reason))
      authentication.handleApiError(reason)
    }
  }
  const submit = async (result: ReviewFeedbackResult) => {
    if (
      submitting.current ||
      busy ||
      abandoned ||
      finished ||
      incompatible.length ||
      refreshFailed ||
      !detail.canReview
    )
      return
    const verdict = wireVerdicts[result.verdict.value as keyof typeof wireVerdicts]
    if (!verdict) return
    submitting.current = true
    setBusy(true)
    setError(null)
    let saved = false
    try {
      const response = await client.sheetComplete(detail.caseId, {
        schemaVersion: 1,
        snapshot: detail.snapshot,
        idempotencyKey: draft.idempotencyKey,
        verdict,
        comment: result.comment || null,
        confirmWithoutComment: verdict < 16 && !result.comment,
        annotations: draft.annotations,
        internalReactionId: draft.reactionId,
      })
      rememberCompletedReview(namespace, accountId, response.review.reviewId)
      saved = true
      clearReviewDraft(window.localStorage, storageKey)
      setFinished(true)
      setChanged(false)
      const next = await onRefresh()
      setDetail(next)
      setDraft({
        ...createEmptyReviewDraft(detail.caseId, createReviewEvidenceFingerprint(next.workspace)),
        annotations: next.annotations,
      })
      setFormVersion((value) => value + 1)
      void queryClient.invalidateQueries({
        predicate: (query) => query.queryKey.includes('review-queue'),
      })
    } catch (reason) {
      authentication.handleApiError(reason)
      if (saved) {
        setRefreshFailed(true)
        setError(
          t`Результат сохранён, но обновить диалог не удалось. Обновите его перед продолжением.`,
        )
      } else if (reason instanceof ApiResponseError && reason.status === 409) {
        setChanged(true)
        store({ ...draft, idempotencyKey: `sheet-${crypto.randomUUID()}` })
        await refresh()
      } else setError(describeReviewError(reason))
    } finally {
      setBusy(false)
      submitting.current = false
    }
  }
  const disabled =
    busy || finished || abandoned || refreshFailed || incompatible.length > 0 || !detail.canReview
  const transferClient = {
    transferPreview: (_queueId: string, entryId: string, snapshot: string) =>
      client.sheetTransferPreview(detail.caseId, entryId, snapshot),
    transfer: (_queueId: string, request: Parameters<ReviewQueueClient['transfer']>[1]) => {
      const { claimToken, ...rest } = request
      return client.sheetTransfer(detail.caseId, { ...rest, snapshot: claimToken })
    },
  }
  const entryActions = detail.pending
    ? (entryId: string) => (
        <ReviewTransfer
          client={transferClient}
          queueId={detail.caseId}
          entryId={entryId}
          claimToken={detail.snapshot}
          disabled={disabled}
          onBusy={setBusy}
          onDone={async (result) => {
            if (result.mode === 'move') {
              setAbandoned(true)
              setMovedTo(result.targetLabel)
            }
            setChanged(false)
            await refresh()
          }}
        />
      )
    : undefined
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-small">
        <span>{detail.workspace.branches.map((branch) => branch.problemNumber).join(' · ')}</span>
        <span>{detail.pending ? t`Ожидает проверки` : t`Проверена`}</span>
        {detail.currentReview && (
          <span>
            {detail.currentReview.teacherName} ·{' '}
            {writtenReviewVerdict(detail.currentReview.verdict).symbol}
          </span>
        )}
      </div>
      {changed && (
        <div
          role="alert"
          className="rounded border border-status-warning-border bg-status-warning-surface p-3"
        >
          <p>
            <Trans>
              Работа уже проверена или материалы изменились. Переписка обновлена. Ваш черновик
              сохранён; просмотрите изменения перед отправкой своего результата.
            </Trans>
          </p>
        </div>
      )}
      {error && <p role="alert">{error}</p>}
      {refreshFailed && (
        <Button variant="outline" disabled={busy} onClick={() => void refresh()}>
          <Trans>Обновить диалог</Trans>
        </Button>
      )}
      {!storageAvailable && (
        <p role="alert">
          <Trans>Не удалось сохранить черновик на устройстве. Не закрывайте страницу.</Trans>
        </p>
      )}
      {incompatible.length > 0 && (
        <div role="alert" className="space-y-2">
          <p>
            <Trans>
              Часть пометок относится к материалам, которые изменились. Удалите эти пометки и
              проверьте текущие фотографии.
            </Trans>
          </p>
          <Button
            variant="outline"
            disabled={busy}
            onClick={() =>
              store({
                ...draft,
                annotations: draft.annotations.filter((item) =>
                  attachmentIds.has(item.attachmentId),
                ),
                idempotencyKey: `sheet-${crypto.randomUUID()}`,
              })
            }
          >
            <Trans>Удалить несовместимые пометки</Trans>
          </Button>
        </div>
      )}
      <ThreePaneReview
        evidence={
          <div className="space-y-4">
            <section aria-label={t`Полная переписка`} className="space-y-2">
              <HistoryEvents
                events={messages}
                openReviews={false}
                renderBody={(event) => {
                  const entry = event.entryId ? evidence.get(event.entryId) : undefined
                  return entry ? (
                    <ReviewEvidenceEntry
                      entry={entry}
                      mediaClient={mediaClient}
                      annotations={draft.annotations}
                      onAnnotationChange={annotate}
                      disabled={disabled}
                      entryActions={entryActions}
                    />
                  ) : undefined
                }}
              />
              {conversation.isFetching && (
                <p role="status">
                  <Trans>Загружаем переписку…</Trans>
                </p>
              )}
              {conversation.error && (
                <>
                  <p role="alert">{describeReviewError(conversation.error)}</p>
                  <Button
                    variant="outline"
                    onClick={() =>
                      void (conversation.isFetchNextPageError
                        ? conversation.fetchNextPage()
                        : conversation.refetch())
                    }
                  >
                    <Trans>Повторить загрузку переписки</Trans>
                  </Button>
                </>
              )}
            </section>
          </div>
        }
        feedback={
          finished || abandoned ? (
            <div className="space-y-2">
              <p role="status">
                {finished
                  ? t`Результат отправлен`
                  : movedTo
                    ? t`Посылка перенесена в ${movedTo}`
                    : t`Вы отказались от этой проверки`}
              </p>
              <Button
                variant="outline"
                disabled={refreshFailed || !detail.canReview}
                onClick={() => {
                  setFinished(false)
                  setAbandoned(false)
                  setMovedTo(null)
                }}
              >
                <Trans>Проверить снова</Trans>
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              {detail.pending && (
                <AiReviewPanel
                  workspace={detail.workspace}
                  caseId={detail.caseId}
                  draft={draft}
                  onDraftChange={edit}
                  disabled={disabled}
                  active={active}
                />
              )}
              <ReviewFeedbackForm
                key={formVersion}
                draft={draft}
                hotkeys={active}
                disabled={disabled}
                initialDraft={{
                  verdictValue: draft.verdictValue,
                  comment: draft.comment,
                  reactionId: draft.reactionId,
                }}
                verdicts={scales[detail.workspace.verdictMode ?? 'verdict_plus_steps']}
                onDraftChange={edit}
                onSubmit={(result) => void submit(result)}
                submitLabel={changed ? t`Отправить мой результат` : undefined}
              />
              <Button variant="ghost" disabled={busy} onClick={() => setAbandoned(true)}>
                <Trans>Отказаться от проверки</Trans>
              </Button>
            </div>
          )
        }
        queue={
          <span className="text-caption text-muted-foreground">
            {detail.workspace.branches[0]?.courseName} · {detail.workspace.branches[0]?.groupName}
          </span>
        }
      />
    </div>
  )
}
