import { t as translate } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { formatDateTime } from '@vmsh/i18n'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { z } from 'zod'
import {
  PageLayout,
  PageStatePanel,
  createReviewQueueClient,
  createWrittenMaterialReassignmentClient,
  useAuthentication,
  useAuthenticatedPrincipal,
} from '@vmsh/app-shell'
import {
  createBrowserStorageNamespace,
  ApiResponseError,
  type ReviewHistoryDetailResponse,
  type ReviewAnnotationManifest,
} from '@vmsh/contracts'
import {
  ReviewFeedbackForm,
  fullVerdictScale,
  binaryVerdictScale,
  ternaryVerdictScale,
  writtenReviewVerdict,
  type ReviewFeedbackResult,
} from '@vmsh/product'
import { Button, Input, Label } from '@vmsh/ui'
import { SemanticMathDocument } from '@vmsh/content'
import { StatisticsStudentSearch } from './statistics-student-search'
import { ReviewAttachmentImage } from './review-workspace-page'
import { createEmptyReviewDraft, reviewDraftSchema } from './review-draft'
import { describeReviewError } from './review-errors'
import { rememberCompletedReview } from './last-completed-review'
import { ReviewConversation } from './review-conversation'
import type { HistorySearch } from './review-history-search'

function historyError(error: unknown): string {
  return error instanceof ApiResponseError
    ? translate`${error.message} Код обращения: ${error.requestId}.`
    : describeReviewError(error)
}
const verdictValues = [
  'rejected',
  'minus-dot',
  'minus-plus',
  'half',
  'plus-minus',
  'plus-dot',
  'plus',
]
const storedSchema = z.object({
  draft: reviewDraftSchema,
  latest: z.string(),
  version: z.number().int().positive(),
})

export function StaffReviewHistoryPage({
  search,
  onSearch,
}: {
  search: HistorySearch
  onSearch: (search: HistorySearch, replace?: boolean) => void
}) {
  const auth = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  const client = useMemo(
    () => createReviewQueueClient(auth.client.runtime, { refreshSession: () => auth.refresh() }),
    [auth],
  )
  const scroll = useRef(0)
  const query = Object.fromEntries(
    Object.entries(search)
      .filter(([key, value]) => key !== 'review' && value !== undefined)
      .map(([key, value]) => [key, String(value)]),
  ) as Record<string, string>
  const history = useQuery({
    queryKey: ['review-history', principal.accountId, query],
    queryFn: ({ signal }) => client.history(query, { signal }),
  })
  const scrollKey = `${createBrowserStorageNamespace(auth.client.runtime)}:review-history-scroll:${principal.accountId}:${JSON.stringify(query)}`
  const options = history.data?.options
  useEffect(() => {
    if (
      options?.courseId &&
      options.lesson !== null &&
      (!search.course || search.lesson === undefined)
    ) {
      // student-results.md: default scope must preserve the Back destination.
      onSearch({ ...search, course: options.courseId, lesson: options.lesson }, true)
    }
  }, [options, search, onSearch])
  const change = (patch: Partial<HistorySearch>) =>
    onSearch({ ...search, cursor: undefined, ...patch })
  const close = () => {
    try {
      scroll.current = Number(window.sessionStorage.getItem(scrollKey) ?? scroll.current)
    } catch {
      /* optional position restoration */
    }
    onSearch({ ...search, review: undefined })
    requestAnimationFrame(() => window.scrollTo(0, scroll.current))
  }
  return (
    <PageLayout title={translate`Завершённые проверки`}>
      {search.review ? (
        <CompletedReviewCard key={search.review} reviewId={search.review} onClose={close} />
      ) : (
        <>
          {history.isPending ? (
            <PageStatePanel state="loading" />
          ) : history.error ? (
            <PageStatePanel
              state="error"
              description={historyError(history.error)}
              actionLabel={translate`Повторить`}
              onAction={() => void history.refetch()}
            />
          ) : (
            options && (
              <div className="space-y-4">
                <div className="flex flex-wrap gap-4">
                  <Label>
                    <Trans>Курс</Trans>
                    <select
                      aria-label={translate`Курс`}
                      className="block rounded border border-border bg-surface p-2"
                      value={options.courseId ?? ''}
                      onChange={(e) =>
                        change({
                          course: e.target.value,
                          lesson: undefined,
                          student: undefined,
                          teacher: undefined,
                          problem: undefined,
                        })
                      }
                    >
                      {options.courses.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name}
                        </option>
                      ))}
                    </select>
                  </Label>
                  <Label>
                    <Trans>Занятие</Trans>
                    <select
                      aria-label={translate`Занятие`}
                      className="block rounded border border-border bg-surface p-2"
                      value={options.lesson ?? ''}
                      onChange={(e) =>
                        change({
                          lesson: Number(e.target.value),
                          student: undefined,
                          problem: undefined,
                        })
                      }
                    >
                      {options.lessons.map((n) => (
                        <option key={n} value={n}>
                          {n}
                        </option>
                      ))}
                    </select>
                  </Label>
                  <Label>
                    <Trans>Преподаватель</Trans>
                    <select
                      aria-label={translate`Преподаватель`}
                      disabled={!options.canChooseTeacher}
                      className="block rounded border border-border bg-surface p-2"
                      value={
                        search.teacher ??
                        (options.canChooseTeacher ? '' : (options.teachers[0]?.id ?? ''))
                      }
                      onChange={(e) => change({ teacher: e.target.value || undefined })}
                    >
                      {options.canChooseTeacher && (
                        <option value="">
                          <Trans>Все преподаватели</Trans>
                        </option>
                      )}
                      {options.teachers.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.name}
                        </option>
                      ))}
                    </select>
                  </Label>
                  <Label>
                    <Trans>Задача</Trans>
                    <select
                      aria-label={translate`Задача`}
                      className="block rounded border border-border bg-surface p-2"
                      value={search.problem ?? ''}
                      onChange={(e) => change({ problem: e.target.value || undefined })}
                    >
                      <option value="">
                        <Trans>Все задачи</Trans>
                      </option>
                      {options.problems.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name}
                        </option>
                      ))}
                    </select>
                  </Label>
                </div>
                <StatisticsStudentSearch
                  label={translate`Школьник`}
                  students={options.students}
                  studentId={search.student ?? null}
                  onChange={(id) => change({ student: id ?? undefined })}
                />
                <Label>
                  <Trans>Фрагмент комментария</Trans>
                  <Input
                    type="search"
                    value={search.comment ?? ''}
                    onChange={(e) => change({ comment: e.target.value || undefined })}
                  />
                </Label>
                <Button onClick={() => void history.refetch()}>
                  <Trans>Обновить</Trans>
                </Button>
                <div className="overflow-x-auto">
                  <table className="w-full text-left">
                    <thead>
                      <tr>
                        {[
                          translate`Когда`,
                          translate`Преподаватель`,
                          translate`Школьник`,
                          translate`Задача`,
                          translate`Оценка`,
                          translate`Комментарий`,
                          '',
                        ].map((s, i) => (
                          <th className="p-2" key={i}>
                            {s}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {history.data?.items.map((item) => (
                        <tr className="border-t border-border" key={item.reviewId}>
                          <td className="p-2">{formatDateTime(new Date(item.completedAt))}</td>
                          <td className="p-2">{item.teacherName}</td>
                          <td className="p-2">
                            {item.studentName}
                            {item.isTestStudent && (
                              <span>
                                {' '}
                                <Trans>· Тест учителя</Trans>
                              </span>
                            )}
                          </td>
                          <td className="p-2">
                            {item.problemNumber} · {item.problemTitle}
                            <div>{item.groupName}</div>
                          </td>
                          <td className="p-2">
                            {writtenReviewVerdict(item.verdict).label}
                            {!item.isLatestReview && (
                              <div>
                                <Trans>Устаревшая</Trans>
                              </div>
                            )}
                          </td>
                          <td className="p-2">{item.comment}</td>
                          <td className="p-2">
                            <Button
                              onClick={() => {
                                scroll.current = window.scrollY
                                try {
                                  window.sessionStorage.setItem(scrollKey, String(scroll.current))
                                } catch {
                                  /* optional position restoration */
                                }
                                change({ cursor: search.cursor, review: item.reviewId })
                              }}
                            >
                              <Trans>Перепроверить</Trans>
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {!history.data?.items.length && (
                  <p>
                    <Trans>Завершённых проверок по этим фильтрам нет.</Trans>
                  </p>
                )}
                <div className="flex gap-2">
                  {search.cursor && (
                    <Button onClick={() => change({ cursor: undefined })}>
                      <Trans>В начало списка</Trans>
                    </Button>
                  )}
                  {history.data?.nextCursor && (
                    <Button
                      onClick={() => change({ cursor: history.data?.nextCursor ?? undefined })}
                    >
                      <Trans>Следующие 50</Trans>
                    </Button>
                  )}
                </div>
              </div>
            )
          )}
        </>
      )}
    </PageLayout>
  )
}

export function CompletedReviewCard({
  reviewId,
  onClose,
  readOnly = false,
  seriesProblemId,
  onCorrected,
}: {
  reviewId: string
  onClose: () => void
  readOnly?: boolean
  seriesProblemId?: string
  onCorrected?: (reviewId: string) => void
}) {
  const auth = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  const client = useMemo(
    () => createReviewQueueClient(auth.client.runtime, { refreshSession: () => auth.refresh() }),
    [auth],
  )
  const query = useQuery({
    queryKey: [
      'review-history-detail',
      principal.accountId,
      reviewId,
      readOnly ? seriesProblemId : null,
    ],
    queryFn: ({ signal }) =>
      readOnly && seriesProblemId
        ? client.seriesCurrent(seriesProblemId, reviewId)
        : client.historyDetail(reviewId, { signal }),
    refetchOnWindowFocus: false,
  })
  return (
    <div className="space-y-4">
      {!readOnly && (
        <Button onClick={onClose}>
          <Trans>Назад</Trans>
        </Button>
      )}
      {query.isPending ? (
        <PageStatePanel state="loading" />
      ) : query.error ? (
        <PageStatePanel
          state="error"
          description={historyError(query.error)}
          actionLabel={translate`Обновить`}
          onAction={() => void query.refetch()}
        />
      ) : readOnly ? (
        <ReadOnlyReview detail={query.data.detail} reviewId={reviewId} />
      ) : (
        <CorrectionEditor
          detail={query.data.detail}
          refresh={() => void query.refetch()}
          onClose={onClose}
          {...(onCorrected ? { onCorrected } : {})}
        />
      )}
    </div>
  )
}

function ReadOnlyReview({
  detail,
  reviewId,
}: {
  detail: ReviewHistoryDetailResponse['detail']
  reviewId: string
}) {
  const auth = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  const client = useMemo(
    () => createReviewQueueClient(auth.client.runtime, { refreshSession: () => auth.refresh() }),
    [auth],
  )
  const media = useMemo(
    () =>
      createWrittenMaterialReassignmentClient(auth.client.runtime, {
        refreshSession: () => auth.refresh(),
      }),
    [auth],
  )
  return (
    <section className="space-y-3">
      <h2 className="font-semibold">
        {detail.review.studentName} · {detail.review.problemNumber} ·{' '}
        {writtenReviewVerdict(detail.review.verdict).label}
      </h2>
      {detail.entries.map((entry) => (
        <article key={entry.entryId} className="space-y-2">
          {entry.text && <p className="whitespace-pre-wrap">{entry.text}</p>}
          {entry.attachments.map((a) => (
            <ReviewAttachmentImage
              key={a.attachmentId}
              attachmentId={a.attachmentId}
              entryId={entry.entryId}
              ordinal={a.ordinal}
              annotation={a.annotation}
              annotationDisabled
              editable={false}
              mediaClient={media}
              onAnnotationChange={() => undefined}
            />
          ))}
        </article>
      ))}
      {detail.comment && (
        <p className="whitespace-pre-wrap rounded-lg border border-border p-3">{detail.comment}</p>
      )}
      <ReviewConversation
        client={client}
        reviewId={reviewId}
        accountId={principal.accountId}
        namespace={createBrowserStorageNamespace(auth.client.runtime)}
        threadVersion={detail.threadVersion}
      />
    </section>
  )
}

function CorrectionEditor({
  detail,
  refresh,
  onClose,
  onCorrected,
}: {
  detail: ReviewHistoryDetailResponse['detail']
  refresh: () => void
  onClose: () => void
  onCorrected?: (reviewId: string) => void
}) {
  const auth = useAuthentication()
  const queryClient = useQueryClient()
  const principal = useAuthenticatedPrincipal()
  const namespace = createBrowserStorageNamespace(auth.client.runtime)
  const key = `${namespace}:history-correction:${principal.accountId}:${detail.review.reviewId}`
  const client = useMemo(
    () => createReviewQueueClient(auth.client.runtime, { refreshSession: () => auth.refresh() }),
    [auth],
  )
  const media = useMemo(
    () =>
      createWrittenMaterialReassignmentClient(auth.client.runtime, {
        refreshSession: () => auth.refresh(),
      }),
    [auth],
  )
  const [stored, setStored] = useState(() => {
    try {
      const parsed = storedSchema.safeParse(JSON.parse(window.localStorage.getItem(key) ?? 'null'))
      if (parsed.success) return parsed.data
    } catch {
      /* unavailable storage */
    }
    const draft = createEmptyReviewDraft(detail.review.reviewId, detail.review.reviewId)
    draft.verdictValue = verdictValues[detail.review.verdict - 11] ?? null
    draft.comment = detail.comment
    draft.annotations = detail.entries.flatMap((e) =>
      e.attachments.flatMap((a) => (a.annotation ? [a.annotation] : [])),
    )
    return { draft, latest: detail.latestReviewId, version: detail.threadVersion }
  })
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [storageFailed, setStorageFailed] = useState(false)
  const save = (next: typeof stored) => {
    setStored(next)
    try {
      window.localStorage.setItem(key, JSON.stringify(next))
      setStorageFailed(false)
    } catch {
      setStorageFailed(true)
    }
  }
  const annotations = (id: string, annotation: ReviewAnnotationManifest | null) =>
    save({
      ...stored,
      draft: {
        ...stored.draft,
        annotations: [
          ...stored.draft.annotations.filter((a) => a.attachmentId !== id),
          ...(annotation ? [annotation] : []),
        ],
      },
    })
  const stale = stored.latest !== detail.latestReviewId || stored.version !== detail.threadVersion
  const submit = async (result: ReviewFeedbackResult) => {
    if (busy || stale || detail.blockedBy) return
    const verdict = verdictValues.indexOf(result.verdict.value) + 11
    const newer = detail.latestReviewId !== detail.review.reviewId
    const latest = detail.timeline[0]
    if (
      newer &&
      !window.confirm(
        translate`Более новая проверка: ${latest?.teacherName ?? ''}, ${latest ? formatDateTime(new Date(latest.completedAt)) : ''}, ${latest ? writtenReviewVerdict(latest.verdict).label : ''}. Заменить её вашей оценкой?`,
      )
    )
      return
    save({
      ...stored,
      draft: { ...stored.draft, verdictValue: result.verdict.value, comment: result.comment },
    })
    setBusy(true)
    setError(null)
    try {
      const response = await client.correct(detail.review.reviewId, {
        schemaVersion: 1,
        idempotencyKey: stored.draft.idempotencyKey,
        verdict,
        comment: result.comment || null,
        confirmWithoutComment: verdict < 16 && !result.comment,
        annotations: stored.draft.annotations,
        expectedLatestReviewId: stored.latest,
        expectedThreadVersion: stored.version,
        confirmReplaceNewer: newer,
      })
      rememberCompletedReview(namespace, principal.accountId, response.correction.reviewId)
      onCorrected?.(response.correction.reviewId)
      void queryClient.invalidateQueries({ queryKey: ['review-history', principal.accountId] })
      void queryClient.invalidateQueries({
        queryKey: ['review-history-detail', principal.accountId],
      })
      void queryClient.invalidateQueries({
        queryKey: ['review-conversation', namespace, principal.accountId],
      })
      try {
        window.localStorage.removeItem(key)
      } catch {
        /* completed */
      }
      onClose()
    } catch (cause) {
      setError(historyError(cause))
      auth.handleApiError(cause)
    } finally {
      setBusy(false)
    }
  }
  return (
    <section className="space-y-4">
      <h2>
        {detail.review.studentName} · {detail.review.problemNumber} · {detail.review.problemTitle}
      </h2>
      {!detail.review.isLatestReview && (
        <p role="alert">
          <Trans>
            Вы исправляете устаревшую проверку. Более новые вердикты показаны ниже; их замена
            потребует подтверждения.
          </Trans>
        </p>
      )}
      {!detail.review.isLatestReview && detail.timeline[0] && (
        <p>
          <Trans>Актуальная проверка: {detail.timeline[0].teacherName} · </Trans>
          {formatDateTime(new Date(detail.timeline[0].completedAt))} ·{' '}
          {writtenReviewVerdict(detail.timeline[0].verdict).label}
        </p>
      )}
      {detail.blockedBy && (
        <p role="alert">
          <Trans>Сейчас проверяет {detail.blockedBy}.</Trans>{' '}
          <Button onClick={refresh}>
            <Trans>Обновить</Trans>
          </Button>
        </p>
      )}
      <details>
        <summary>
          <Trans>Условие задачи</Trans>
        </summary>
        {detail.document ? (
          <SemanticMathDocument document={detail.document} />
        ) : (
          <p className="whitespace-pre-wrap">
            {detail.statement || translate`Условие не сохранено для этой работы.`}
          </p>
        )}
      </details>
      <section aria-label={translate`Материалы выбранной проверки`} className="space-y-3">
        <h3>
          <Trans>Материалы выбранной проверки</Trans>
        </h3>
        {detail.entries.map((entry) => (
          <article className="space-y-2" key={entry.entryId}>
            {entry.text && <p className="whitespace-pre-wrap">{entry.text}</p>}
            {entry.attachments.map((a) => (
              <ReviewAttachmentImage
                key={a.attachmentId}
                attachmentId={a.attachmentId}
                entryId={entry.entryId}
                ordinal={a.ordinal}
                annotation={
                  stored.draft.annotations.find((m) => m.attachmentId === a.attachmentId) ?? null
                }
                annotationDisabled={busy}
                editable
                mediaClient={media}
                onAnnotationChange={annotations}
              />
            ))}
          </article>
        ))}
      </section>
      <ReviewConversation
        client={client}
        reviewId={detail.review.reviewId}
        accountId={principal.accountId}
        namespace={namespace}
        threadVersion={detail.threadVersion}
      />
      {storageFailed && (
        <p role="alert">
          <Trans>Браузер не сохраняет черновик. Не закрывайте страницу до отправки.</Trans>
        </p>
      )}
      {error && (
        <p role="alert">
          <Trans>{error} Ваши изменения остаются в форме. </Trans>
          <Button onClick={refresh}>
            <Trans>Обновить данные</Trans>
          </Button>
        </p>
      )}
      {stale && (
        <p role="alert">
          <Trans>Работа изменилась. Черновик сохранён. </Trans>
          <Button
            onClick={() =>
              save({
                ...stored,
                latest: detail.latestReviewId,
                version: detail.threadVersion,
                draft: { ...stored.draft, idempotencyKey: `correction-${crypto.randomUUID()}` },
              })
            }
          >
            <Trans>Ознакомился с обновлениями, продолжить</Trans>
          </Button>
        </p>
      )}
      <ReviewFeedbackForm
        disabled={busy || stale || Boolean(detail.blockedBy)}
        initialDraft={{
          verdictValue: stored.draft.verdictValue,
          comment: stored.draft.comment,
          reactionId: null,
        }}
        onDraftChange={(draft) =>
          save({
            ...stored,
            draft: { ...stored.draft, verdictValue: draft.verdictValue, comment: draft.comment },
          })
        }
        onSubmit={(result) => void submit(result)}
        showInternalReaction={false}
        verdicts={
          detail.verdictMode === 'verdict_plus_minus'
            ? binaryVerdictScale
            : detail.verdictMode === 'verdict_plus_minus_half'
              ? ternaryVerdictScale
              : fullVerdictScale
        }
      />
    </section>
  )
}
