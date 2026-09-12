import { useNavigate } from '@tanstack/react-router'
import { ReviewTransfer } from './review-transfer'
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

import {
  PageLayout,
  PageSection,
  PageStatePanel,
  createReviewQueueClient,
  recordProductAction,
  createWrittenMaterialReassignmentClient,
  useAuthenticatedPrincipal,
  useAuthentication,
  useCompleteReviewMutation,
  useHeartbeatReviewLeaseMutation,
  useReleaseReviewLeaseMutation,
  useReviewLeaseQuery,
} from '@vmsh/app-shell'
import {
  ApiResponseError,
  createBrowserStorageNamespace,
  writtenTeacherReactionIdSchema,
  type ReviewAnnotationManifest,
  type ReviewLease,
  type ReviewTimelineEntry,
  type CompleteReviewResponse,
} from '@vmsh/contracts'
import {
  FeedbackThread,
  ReviewAnnotationEditor,
  ReviewAnnotationViewer,
  ReviewFeedbackForm,
  ThreePaneReview,
  binaryVerdictScale,
  fullVerdictScale,
  ternaryVerdictScale,
  type ReviewFeedbackDraft,
  type ReviewFeedbackResult,
  type ThreadMessageView,
} from '@vmsh/product'
import {
  Alert,
  AlertContent,
  AlertDescription,
  AlertTitle,
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@vmsh/ui'

import {
  clearReviewDraft,
  createEmptyReviewDraft,
  createReviewEvidenceFingerprint,
  readReviewDraft,
  reviewDraftStorageKey,
  writeReviewDraft,
  type ReviewDraft,
} from './review-draft'
import { describeReviewError } from './review-errors'
import { rememberCompletedReview } from './last-completed-review'

const verdictToWire = {
  rejected: 11,
  'minus-dot': 12,
  'minus-plus': 13,
  half: 14,
  'plus-minus': 15,
  'plus-dot': 16,
  plus: 17,
} as const

const verdictsByMode = {
  verdict_plus_minus: binaryVerdictScale,
  verdict_plus_minus_half: ternaryVerdictScale,
  verdict_plus_steps: fullVerdictScale,
} as const

/** Live lease-backed composition of Product/Review--Workspace. */
export function StaffReviewWorkspacePage({ queueId }: { queueId: string }) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  const runtime = authentication.client.runtime
  const client = useMemo(
    () =>
      createReviewQueueClient(runtime, {
        refreshSession: async () => {
          try {
            return await authentication.refresh()
          } catch (error) {
            authentication.handleApiError(error)
            throw error
          }
        },
      }),
    [authentication, runtime],
  )
  const mediaClient = useMemo(
    () =>
      createWrittenMaterialReassignmentClient(runtime, {
        refreshSession: async () => authentication.refresh(),
      }),
    [authentication, runtime],
  )
  const leaseQuery = useReviewLeaseQuery(client, principal, queueId)

  if (leaseQuery.isPending) {
    return <WorkspacePageShell content={<PageStatePanel state="loading" />} />
  }
  if (leaseQuery.error) {
    return (
      <WorkspacePageShell
        content={
          <PageStatePanel
            actionLabel="Повторить"
            description={describeReviewError(leaseQuery.error)}
            onAction={() => void leaseQuery.refetch()}
            state={
              leaseQuery.error instanceof ApiResponseError && leaseQuery.error.status === 403
                ? 'forbidden'
                : 'error'
            }
          />
        }
      />
    )
  }
  if (!leaseQuery.data) return null

  return (
    <LoadedReviewWorkspace
      client={client}
      key={createReviewEvidenceFingerprint(leaseQuery.data.lease)}
      lease={leaseQuery.data.lease}
      mediaClient={mediaClient}
      principal={principal}
      queueId={queueId}
    />
  )
}

export function LoadedReviewWorkspace({
  client,
  lease,
  mediaClient,
  principal,
  queueId,
  inactive = false,
  onCompleted,
  onBusyChange,
  onMoved,
}: {
  client: ReturnType<typeof createReviewQueueClient>
  lease: ReviewLease
  mediaClient: ReturnType<typeof createWrittenMaterialReassignmentClient>
  principal: ReturnType<typeof useAuthenticatedPrincipal>
  queueId: string
  inactive?: boolean
  onCompleted?: (
    response: CompleteReviewResponse,
    draft: ReviewDraft,
    reviewedLease: ReviewLease,
  ) => void
  onBusyChange?: (busy: boolean) => void
  onMoved?: (targetLabel: string, entryId: string, transferredLease: ReviewLease) => void
}) {
  const authentication = useAuthentication()
  const navigate = useNavigate()
  const [transferBusy, setTransferBusy] = useState(false)
  const fingerprint = createReviewEvidenceFingerprint(lease)
  const namespace = createBrowserStorageNamespace(authentication.client.runtime)
  const storageKey = reviewDraftStorageKey(
    namespace,
    principal.accountId,
    lease.logicalCaseId,
    fingerprint,
  )
  const [draft, setDraft] = useState<ReviewDraft>(() => {
    const restored = readReviewDraft(window.localStorage, storageKey, {
      logicalCaseId: lease.logicalCaseId,
      evidenceFingerprint: fingerprint,
    })
    return restored ?? createEmptyReviewDraft(lease.logicalCaseId, fingerprint)
  })
  const [storageAvailable, setStorageAvailable] = useState(true)
  const heartbeat = useHeartbeatReviewLeaseMutation(client, principal, queueId)
  const release = useReleaseReviewLeaseMutation(client, principal, queueId)
  const complete = useCompleteReviewMutation(client, principal, queueId)
  const currentLease = heartbeat.data?.lease ?? lease
  const leaseLost = Boolean(heartbeat.error)

  useEffect(() => {
    if (!inactive) onBusyChange?.(complete.isPending || release.isPending || transferBusy)
  }, [inactive, complete.isPending, release.isPending, transferBusy, onBusyChange])

  useEffect(() => {
    const renew = () => {
      if (!heartbeat.isPending) {
        heartbeat.mutate(currentLease.claimToken, {
          onError: (error) => authentication.handleApiError(error),
        })
      }
    }
    const timer = window.setInterval(renew, 5 * 60_000)
    const onVisibility = () => {
      if (document.visibilityState === 'visible') renew()
    }
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [authentication, currentLease.claimToken, heartbeat])

  const updateDraft = (next: ReviewFeedbackDraft) => {
    setDraft((current) => {
      const parsedReaction = writtenTeacherReactionIdSchema.safeParse(next.reactionId)
      const updated = {
        ...current,
        ...next,
        reactionId: parsedReaction.success ? parsedReaction.data : null,
        updatedAt: new Date().toISOString(),
      }
      setStorageAvailable(writeReviewDraft(window.localStorage, storageKey, updated))
      return updated
    })
  }

  const updateAnnotation = (attachmentId: string, annotation: ReviewAnnotationManifest | null) => {
    setDraft((current) => {
      const annotations = current.annotations.filter(
        (candidate) => candidate.attachmentId !== attachmentId,
      )
      if (annotation) annotations.push(annotation)
      const updated = {
        ...current,
        annotations,
        updatedAt: new Date().toISOString(),
      }
      setStorageAvailable(writeReviewDraft(window.localStorage, storageKey, updated))
      return updated
    })
  }

  const submit = async (result: ReviewFeedbackResult) => {
    if (inactive || complete.isPending || leaseLost || transferBusy) return
    const verdict = verdictToWire[result.verdict.value as keyof typeof verdictToWire]
    const reaction = writtenTeacherReactionIdSchema.safeParse(result.reactionId)
    if (!verdict || (result.reactionId !== null && !reaction.success)) return
    const branches = currentLease.branches.flatMap((branch) => {
      const evidence = currentLease.evidenceBranches.find(
        (candidate) => candidate.queueId === branch.queueId,
      )
      if (!evidence?.thread || evidence.thread.entries.length === 0) return []
      return [
        {
          queueId: branch.queueId,
          leaseVersion: branch.leaseVersion,
          threadId: evidence.thread.threadId,
          threadVersion: evidence.thread.threadVersion,
          evidence: evidence.thread.entries.map((entry) => ({
            entryId: entry.entryId,
            entryVersion: entry.entryVersion,
          })),
        },
      ]
    })
    if (branches.length !== currentLease.branches.length) return

    complete.reset()
    try {
      const response = await complete.mutateAsync({
        schemaVersion: 1,
        claimToken: currentLease.claimToken,
        idempotencyKey: draft.idempotencyKey,
        verdict,
        comment: result.comment || null,
        confirmWithoutComment: verdict < 16 && result.comment === '',
        branches,
        annotations: draft.annotations,
        internalReactionId: reaction.success ? reaction.data : null,
      })
      const queueId = currentLease.branches[0]?.queueId
      if (queueId) recordProductAction('review.verdict', { type: 'submission', id: queueId })
      clearReviewDraft(window.localStorage, storageKey)
      rememberCompletedReview(namespace, principal.accountId, response.review.reviewId)
      if (onCompleted) onCompleted(response, draft, currentLease)
      else await navigate({ to: '/review' })
    } catch (error) {
      authentication.handleApiError(error)
    }
  }

  const abandon = async () => {
    if (release.isPending) return
    release.reset()
    try {
      await release.mutateAsync(currentLease.claimToken)
      await navigate({ to: '/review' })
    } catch (error) {
      authentication.handleApiError(error)
    }
  }

  const messages = timelineMessages(
    currentLease,
    mediaClient,
    draft.annotations,
    updateAnnotation,
    inactive || complete.isPending || leaseLost || transferBusy,
    false,
    (entryId) => (
      <ReviewTransfer
        client={client}
        queueId={queueId}
        entryId={entryId}
        claimToken={currentLease.claimToken}
        disabled={inactive || complete.isPending || leaseLost || transferBusy}
        onBusy={(busy) => {
          setTransferBusy(busy)
          onBusyChange?.(busy)
        }}
        onDone={async (result) => {
          if (result.mode === 'move') {
            if (onMoved) onMoved(result.targetLabel, result.sourceEntryId, currentLease)
            else await navigate({ to: '/review' })
          } else await heartbeat.mutateAsync(currentLease.claimToken)
        }}
      />
    ),
  )
  const first = currentLease.branches[0]!
  const errors = complete.error ?? release.error

  return (
    <PageLayout
      actions={
        <Button disabled={release.isPending} onClick={() => void abandon()} variant="ghost">
          Отказаться от проверки
        </Button>
      }
      description={`${currentLease.student.displayName} · ${first.courseName ?? 'Курс'} · ${first.groupName}`}
      eyebrow={`${first.problemNumber} · ${first.problemTitle}`}
      title="Проверка работы"
      width="wide"
    >
      <div className="space-y-3">
        {!storageAvailable ? (
          <Alert tone="danger" role="alert">
            <AlertContent>
              <AlertTitle>Не удалось сохранить черновик на устройстве</AlertTitle>
              <AlertDescription>
                Не закрывайте страницу и скопируйте комментарий перед продолжением.
              </AlertDescription>
            </AlertContent>
          </Alert>
        ) : null}
        {leaseLost ? (
          <Alert tone="danger" role="alert">
            <AlertContent>
              <AlertTitle>Блокировка проверки потеряна</AlertTitle>
              <AlertDescription>
                Черновик сохранён. Вернитесь в очередь и откройте работу заново.
              </AlertDescription>
            </AlertContent>
          </Alert>
        ) : null}
        {errors ? (
          <Alert tone="danger" role="alert">
            <AlertContent>
              <AlertTitle>Проверка не сохранена</AlertTitle>
              <AlertDescription>{describeReviewError(errors)}</AlertDescription>
            </AlertContent>
          </Alert>
        ) : null}
        <ThreePaneReview
          evidence={
            <PageSection title="Работа и переписка">
              <Card>
                <CardHeader className="flex-row items-center justify-between">
                  <CardTitle>{messages.length} сообщений</CardTitle>
                  <Badge variant="success">Взята вами</Badge>
                </CardHeader>
                <CardContent>
                  <FeedbackThread messages={messages} />
                </CardContent>
              </Card>
            </PageSection>
          }
          feedback={
            <ReviewFeedbackForm
              disabled={inactive || complete.isPending || leaseLost || transferBusy}
              initialDraft={{
                verdictValue: draft.verdictValue,
                comment: draft.comment,
                reactionId: draft.reactionId,
              }}
              onDraftChange={updateDraft}
              onSubmit={(result) => void submit(result)}
              verdicts={verdictsByMode[currentLease.verdictMode ?? 'verdict_plus_steps']}
            />
          }
          queue={<BranchSummary lease={currentLease} />}
        />
      </div>
    </PageLayout>
  )
}

function BranchSummary({ lease }: { lease: ReviewLease }) {
  return (
    <div className="flex flex-wrap gap-2 text-caption text-muted-foreground">
      {lease.branches.map((branch) => (
        <span key={branch.queueId}>
          {branch.problemNumber} · {branch.groupName}
        </span>
      ))}
    </div>
  )
}

export function ReviewReadOnlyEvidence({
  lease,
  mediaClient,
  annotations,
}: {
  lease: ReviewLease
  mediaClient: ReturnType<typeof createWrittenMaterialReassignmentClient>
  annotations: ReviewAnnotationManifest[]
}) {
  return (
    <FeedbackThread
      messages={timelineMessages(lease, mediaClient, annotations, () => undefined, true)}
    />
  )
}

function timelineMessages(
  lease: ReviewLease,
  mediaClient: ReturnType<typeof createWrittenMaterialReassignmentClient>,
  annotations: ReviewAnnotationManifest[],
  onAnnotationChange: (attachmentId: string, annotation: ReviewAnnotationManifest | null) => void,
  annotationDisabled: boolean,
  readOnly = false,
  entryActions?: (entryId: string) => ReactNode,
): ThreadMessageView[] {
  const editableAttachmentIds = new Set(
    readOnly
      ? []
      : lease.evidenceBranches.flatMap((branch) =>
          branch.thread
            ? branch.thread.entries.flatMap((entry) =>
                entry.attachments.map((attachment) => attachment.attachmentId),
              )
            : [],
        ),
  )
  const annotationByAttachment = new Map(
    annotations.map((annotation) => [annotation.attachmentId, annotation]),
  )
  return lease.evidenceBranches
    .flatMap((evidenceBranch) => {
      const branch = lease.branches.find(
        (candidate) => candidate.queueId === evidenceBranch.queueId,
      )
      if (!branch || !evidenceBranch.thread) return []
      return evidenceBranch.thread.timelineEntries.map((entry) => ({
        submittedAt: entry.submittedAt,
        message: {
          id: `${evidenceBranch.queueId}:${entry.entryId}`,
          author: {
            kind: entry.authorKind === 'system' ? ('admin' as const) : entry.authorKind,
            ...(entry.authorKind === 'student'
              ? { name: lease.student.displayName }
              : entry.authorKind === 'system'
                ? { name: 'Система' }
                : {}),
          },
          at: formatMessageTime(entry.submittedAt),
          channel: 'pwa' as const,
          origin: {
            courseName: branch.courseName ?? 'Курс',
            groupName: branch.groupName,
            taskNumber: branch.problemNumber,
          },
          body: (
            <>
              <TimelineEntryBody
                annotationByAttachment={annotationByAttachment}
                annotationDisabled={annotationDisabled}
                editableAttachmentIds={editableAttachmentIds}
                entry={entry}
                key={entry.entryId}
                mediaClient={mediaClient}
                onAnnotationChange={onAnnotationChange}
              />
              {!readOnly &&
                evidenceBranch.thread?.entries.some(
                  (pending) => pending.entryId === entry.entryId,
                ) &&
                entryActions?.(entry.entryId)}
            </>
          ),
        } satisfies ThreadMessageView,
      }))
    })
    .sort((left, right) => left.submittedAt.localeCompare(right.submittedAt))
    .map((item) => item.message)
}

function TimelineEntryBody({
  annotationByAttachment,
  annotationDisabled,
  editableAttachmentIds,
  entry,
  mediaClient,
  onAnnotationChange,
}: {
  annotationByAttachment: Map<string, ReviewAnnotationManifest>
  annotationDisabled: boolean
  editableAttachmentIds: Set<string>
  entry: ReviewTimelineEntry
  mediaClient: ReturnType<typeof createWrittenMaterialReassignmentClient>
  onAnnotationChange: (attachmentId: string, annotation: ReviewAnnotationManifest | null) => void
}) {
  return (
    <div className="space-y-2">
      {entry.text ? <p className="whitespace-pre-wrap">{entry.text}</p> : null}
      {entry.attachments.length ? (
        <div className="grid gap-2 sm:grid-cols-2">
          {entry.attachments.map((attachment) => (
            <ReviewAttachmentImage
              attachmentId={attachment.attachmentId}
              annotation={annotationByAttachment.get(attachment.attachmentId) ?? null}
              annotationDisabled={annotationDisabled}
              editable={editableAttachmentIds.has(attachment.attachmentId)}
              entryId={entry.entryId}
              key={attachment.attachmentId}
              mediaClient={mediaClient}
              ordinal={attachment.ordinal}
              onAnnotationChange={onAnnotationChange}
            />
          ))}
        </div>
      ) : null}
    </div>
  )
}

export function ReviewAttachmentImage({
  attachmentId,
  annotation,
  annotationDisabled,
  editable,
  entryId,
  mediaClient,
  ordinal,
  onAnnotationChange,
}: {
  attachmentId: string
  annotation: ReviewAnnotationManifest | null
  annotationDisabled: boolean
  editable: boolean
  entryId: string
  mediaClient: ReturnType<typeof createWrittenMaterialReassignmentClient>
  ordinal: number
  onAnnotationChange: (attachmentId: string, annotation: ReviewAnnotationManifest | null) => void
}) {
  const [source, setSource] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)
  const placeholder = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(editable || typeof IntersectionObserver === 'undefined')
  useEffect(() => {
    if (visible || !placeholder.current) return
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setVisible(true)
          observer.disconnect()
        }
      },
      { rootMargin: '300px' },
    )
    observer.observe(placeholder.current)
    return () => observer.disconnect()
  }, [visible])
  useEffect(() => {
    if (!visible) return
    const controller = new AbortController()
    let objectUrl: string | null = null
    void mediaClient
      .attachmentMedia(entryId, attachmentId, { signal: controller.signal })
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob)
        setSource(objectUrl)
      })
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === 'AbortError')) setFailed(true)
      })
    return () => {
      controller.abort()
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [attachmentId, entryId, mediaClient, visible])

  if (failed)
    return <p className="text-caption text-status-error">Не удалось загрузить страницу.</p>
  if (!source)
    return (
      <div
        ref={placeholder}
        aria-label="Загружаем страницу"
        className="h-48 animate-pulse rounded-md bg-surface-sunken"
      />
    )
  if (editable) {
    return (
      <ReviewAnnotationEditor
        attachmentId={attachmentId}
        disabled={annotationDisabled}
        imageAlt={`Страница решения ${ordinal + 1}`}
        imageSource={source}
        initialManifest={annotation}
        onChange={(next) => onAnnotationChange(attachmentId, next)}
      />
    )
  }
  if (annotation)
    return (
      <ReviewAnnotationViewer
        imageAlt={`Страница решения ${ordinal + 1}`}
        imageSource={source}
        manifest={annotation}
      />
    )
  return (
    <img
      alt={`Страница решения ${ordinal + 1}`}
      className="max-h-[42rem] w-full rounded-md border border-border bg-surface object-contain"
      src={source}
    />
  )
}

/** Immutable session snapshot, without review leases/editors; docs/serial-review-feed.md. */
export function ReviewedWorkSnapshot({
  lease,
  annotations,
  comment,
  verdict,
  mediaClient,
}: {
  lease: ReviewLease
  annotations: ReviewAnnotationManifest[]
  comment: string
  verdict: string
  mediaClient: ReturnType<typeof createWrittenMaterialReassignmentClient>
}) {
  return (
    <section className="space-y-3">
      <h2 className="text-subtitle font-semibold">
        {lease.student.displayName} · {verdict}
      </h2>
      <FeedbackThread
        messages={timelineMessages(lease, mediaClient, annotations, () => undefined, true, true)}
      />
      {comment && (
        <p className="whitespace-pre-wrap rounded-lg border border-border p-3">{comment}</p>
      )}
    </section>
  )
}

function formatMessageTime(value: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

function WorkspacePageShell({ content }: { content: React.ReactNode }) {
  return (
    <PageLayout eyebrow="Письменная задача" title="Проверка работы" width="wide">
      {content}
    </PageLayout>
  )
}
