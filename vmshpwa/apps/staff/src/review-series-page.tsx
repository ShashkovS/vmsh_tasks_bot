import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { SemanticMathDocument } from '@vmsh/content'
import {
  createReviewQueueClient,
  createWrittenMaterialReassignmentClient,
  PageStatePanel,
  useAuthentication,
  useAuthenticatedPrincipal,
} from '@vmsh/app-shell'
import {
  ApiResponseError,
  type CompleteReviewResponse,
  type ReviewLease,
  reviewQueueQueryKeys,
  createBrowserStorageNamespace,
} from '@vmsh/contracts'
import { Button } from '@vmsh/ui'
import { LoadedReviewWorkspace, ReviewedWorkSnapshot } from './review-workspace-page'
import { type ReviewDraft } from './review-draft'
import { writtenReviewVerdict } from '@vmsh/product'
import { CompletedReviewCard } from './review-history-page'
import { lastCompletedReview } from './last-completed-review'
import { allReviewItems, seriesCandidates } from './review-series-model'
import { describeReviewError } from './review-errors'

type PreparedWork = { queueId: string; lease: ReviewLease }
type FinishedWork = {
  reviewId: string
  materialKey: string
  lease?: ReviewLease
  draft?: ReviewDraft
  verdict?: number
  movedTo?: string
}
const materialKey = (lease: ReviewLease) =>
  lease.evidenceBranches
    .flatMap((b) => b.thread?.entries.map((e) => e.entryId) ?? [])
    .sort()
    .join(',')

/** One active + one rendered next lease, per docs/serial-review.md (Phase 6). */
export function StaffReviewSeriesPage({ problemId }: { problemId: string }) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  const runtime = authentication.client.runtime
  const queryClient = useQueryClient()
  // Transport belongs to this mounted series; auth refresh must not release
  // the prepared leases or recreate already loaded image URLs.
  const [client] = useState(() =>
    createReviewQueueClient(runtime, {
      refreshSession: () => authentication.refresh(),
    }),
  )
  const [mediaClient] = useState(() =>
    createWrittenMaterialReassignmentClient(runtime, {
      refreshSession: () => authentication.refresh(),
    }),
  )
  const [works, setWorks] = useState<PreparedWork[]>([])
  const owned = useRef<PreparedWork[]>([])
  const completed = useRef(new Set<string>())
  const busy = useRef(false)
  const alive = useRef(true)
  const generation = useRef(0)
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const namespace = createBrowserStorageNamespace(runtime)
  const [previous, setPrevious] = useState<string | null>(() =>
    lastCompletedReview(namespace, principal.accountId),
  )
  const [correcting, setCorrecting] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [feed, setFeed] = useState<FinishedWork[]>([])
  const [historyCursor, setHistoryCursor] = useState<string | null | undefined>(undefined)
  const [historyBusy, setHistoryBusy] = useState(false)
  const prependHeight = useRef<number | null>(null)
  const correctionFocus = useRef<HTMLElement | null>(null)
  const feedElements = useRef(new Map<string, HTMLElement>())
  const correctionMaterial = useRef<string | null>(null)
  const currentElement = useRef<HTMLDivElement>(null)
  const toolbarElement = useRef<HTMLDivElement>(null)
  const advanceScroll = useRef(false)
  const correctionScroll = useRef(0)
  const openCorrection = (id: string) => {
    correctionMaterial.current = feed.find((item) => item.reviewId === id)?.materialKey ?? null
    correctionFocus.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null
    correctionScroll.current = window.scrollY
    setEditingId(id)
    setCorrecting(true)
  }
  const closeCorrection = () => {
    setCorrecting(false)
    setEditingId(null)
    requestAnimationFrame(() => {
      const previousFocus = correctionFocus.current
      if (previousFocus?.isConnected) previousFocus.focus({ preventScroll: true })
      else if (correctionMaterial.current)
        feedElements.current
          .get(correctionMaterial.current)
          ?.querySelector('button')
          ?.focus({ preventScroll: true })
      window.scrollTo({ top: correctionScroll.current, behavior: 'instant' })
    })
  }
  const [savingReview, setSavingReview] = useState(false)
  const skipBusy = useRef(false)
  useLayoutEffect(() => {
    if (!correcting || !correctionMaterial.current) return
    const element = feedElements.current.get(correctionMaterial.current)
    if (element)
      window.scrollTo({
        top:
          window.scrollY +
          element.getBoundingClientRect().top -
          (toolbarElement.current?.offsetHeight ?? 0) -
          8,
        behavior: 'instant',
      })
  }, [correcting, editingId])
  const conditionQueue = works[0]?.lease.branches.find((b) => b.problemId === problemId)?.queueId
  const conditionEntry = works[0]?.lease.evidenceBranches.find((b) => b.queueId === conditionQueue)
    ?.thread?.entries[0]?.entryId
  const condition = useQuery({
    queryKey: ['series-condition', principal.accountId, problemId, conditionEntry],
    queryFn: () => client.seriesCondition(problemId, conditionEntry),
  })
  const loadHistory = async () => {
    if (historyBusy || historyCursor === null) return
    setHistoryBusy(true)
    try {
      const page = await client.seriesHistory(problemId, historyCursor)
      prependHeight.current = document.documentElement.scrollHeight
      setFeed((items) => {
        const seen = new Set(items.map((i) => i.materialKey))
        return [...page.items.filter((i) => !seen.has(i.materialKey)).reverse(), ...items]
      })
      setHistoryCursor(page.nextCursor)
    } catch (error) {
      setMessage(describeReviewError(error))
    } finally {
      setHistoryBusy(false)
    }
  }
  useLayoutEffect(() => {
    if (prependHeight.current !== null) {
      window.scrollBy(0, document.documentElement.scrollHeight - prependHeight.current)
      prependHeight.current = null
    }
  }, [feed])

  const fill = useCallback(async () => {
    if (busy.current || owned.current.length >= 2) return
    busy.current = true
    const attempt = generation.current
    setLoading(true)
    setMessage(null)
    try {
      const items = await queryClient.fetchQuery({
        queryKey: [...reviewQueueQueryKeys.all(principal), 'series-candidates', problemId],
        queryFn: ({ signal }) => allReviewItems(client, signal),
        staleTime: 0,
      })
      const excluded = new Set([
        ...completed.current,
        ...owned.current.map((item) => item.lease.logicalCaseId),
      ])
      for (const item of seriesCandidates(items, problemId, excluded)) {
        if (!alive.current || attempt !== generation.current || owned.current.length >= 2) break
        try {
          const { lease } = await client.claim(item.queueId)
          if (!alive.current || attempt !== generation.current) {
            await client.release(item.queueId, lease.claimToken)
            break
          }
          const work = { queueId: item.queueId, lease }
          owned.current = [...owned.current, work]
          setWorks(owned.current)
        } catch (error) {
          if (error instanceof ApiResponseError && [404, 409].includes(error.status)) {
            if (alive.current) setMessage('Эту работу уже проверяют. Выбираем следующую…')
            continue
          }
          throw error
        }
      }
    } catch (error) {
      if (alive.current) {
        setMessage(describeReviewError(error))
        authentication.handleApiError(error)
      }
    } finally {
      if (attempt === generation.current) {
        busy.current = false
        if (alive.current) setLoading(false)
      }
    }
  }, [authentication, client, principal, problemId, queryClient])

  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
      generation.current += 1
      busy.current = false
      const remaining = owned.current
      owned.current = []
      for (const work of remaining)
        void client.release(work.queueId, work.lease.claimToken).catch(() => undefined)
    }
  }, [client])
  useEffect(() => {
    void fill()
  }, [fill, works.length])

  const finish = (
    work: PreparedWork,
    response: CompleteReviewResponse,
    draft: ReviewDraft,
    reviewedLease = work.lease,
  ) => {
    setSavingReview(false)
    completed.current.add(work.lease.logicalCaseId)
    setPrevious(response.review.reviewId)
    setFeed((items) => [
      ...items.filter((i) => i.materialKey !== materialKey(reviewedLease)),
      {
        reviewId: response.review.reviewId,
        materialKey: materialKey(reviewedLease),
        lease: reviewedLease,
        draft,
        verdict: response.review.verdict,
      },
    ])
    owned.current = owned.current.filter((item) => item.queueId !== work.queueId)
    setWorks(owned.current)
    advanceScroll.current = true
  }
  const moved = (
    work: PreparedWork,
    targetLabel: string,
    entryId: string,
    transferredLease = work.lease,
  ) => {
    setSavingReview(false)
    completed.current.add(work.lease.logicalCaseId)
    const lease = {
      ...transferredLease,
      evidenceBranches: transferredLease.evidenceBranches.map((b) =>
        b.thread
          ? {
              ...b,
              thread: {
                ...b.thread,
                entries: b.thread.entries.filter((e) => e.entryId === entryId),
                timelineEntries: b.thread.timelineEntries.filter((e) => e.entryId === entryId),
              },
            }
          : b,
      ),
    }
    setFeed((items) => [
      ...items,
      { reviewId: `moved-${entryId}`, materialKey: entryId, lease, movedTo: targetLabel },
    ])
    owned.current = owned.current.filter((item) => item.queueId !== work.queueId)
    setWorks(owned.current)
    advanceScroll.current = true
    // The transferred entry may have affected a prefetched logical case.
    for (const next of owned.current)
      void client
        .heartbeat(next.queueId, next.lease.claimToken)
        .then((result) => {
          owned.current = owned.current.map((item) =>
            item.queueId === next.queueId ? { ...item, lease: result.lease } : item,
          )
          if (alive.current) setWorks(owned.current)
        })
        .catch(() => undefined)
  }
  useEffect(() => {
    if (advanceScroll.current && works.length) {
      advanceScroll.current = false
      requestAnimationFrame(() => {
        if (currentElement.current)
          window.scrollTo({
            top:
              window.scrollY +
              currentElement.current.getBoundingClientRect().top -
              (toolbarElement.current?.offsetHeight ?? 0) -
              8,
            behavior: 'instant',
          })
      })
    }
  }, [works])
  const skip = async () => {
    if (savingReview || skipBusy.current) return
    const current = owned.current[0]
    if (!current) {
      void fill()
      return
    }
    skipBusy.current = true
    try {
      await client.release(current.queueId, current.lease.claimToken)
    } catch (error) {
      if (!(error instanceof ApiResponseError && [404, 409].includes(error.status))) {
        setMessage(describeReviewError(error))
        return
      }
    } finally {
      skipBusy.current = false
    }
    completed.current.add(current.lease.logicalCaseId)
    owned.current = owned.current.filter((work) => work.queueId !== current.queueId)
    setWorks(owned.current)
  }
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if (event.repeat || savingReview || !(event.ctrlKey || event.metaKey) || !event.altKey) return
      if (event.code === 'ArrowLeft' && previous) {
        event.preventDefault()
        if (correcting) closeCorrection()
        else openCorrection(previous)
      }
      if (event.code === 'ArrowRight' && !correcting) {
        event.preventDefault()
        void skip()
      }
    }
    window.addEventListener('keydown', key)
    return () => window.removeEventListener('keydown', key)
  })
  return (
    <div className="mx-auto max-w-[1500px] px-4 py-3">
      <h1 className="text-subtitle font-semibold">{condition.data?.label ?? problemId}</h1>
      <details className="my-3 rounded-lg border border-border p-3">
        <summary className="cursor-pointer font-medium">Условие задачи</summary>
        {condition.data?.document ? (
          <SemanticMathDocument document={condition.data.document} />
        ) : (
          <p className="py-3">
            {condition.isPending ? 'Загружаем условие…' : 'Условие проверяемой версии недоступно.'}
          </p>
        )}
      </details>
      <Button
        className="mb-3"
        size="sm"
        variant="outline"
        disabled={historyBusy || historyCursor === null || correcting}
        onClick={() => void loadHistory()}
      >
        {historyBusy
          ? 'Загружаем…'
          : historyCursor === null
            ? 'Более ранних собственных проверок нет'
            : 'Показать предыдущие 20 проверок'}
      </Button>
      <div
        ref={toolbarElement}
        className="sticky top-0 z-10 flex flex-wrap items-center gap-2 border-b border-border bg-background py-2"
      >
        <Button render={<Link to="/review" />} variant="outline" size="sm">
          К списку задач
        </Button>
        <Button
          disabled={!previous || savingReview}
          onClick={() => {
            if (correcting) closeCorrection()
            else if (previous) openCorrection(previous)
          }}
          variant="outline"
          size="sm"
        >
          {correcting ? 'Продолжить серию' : 'Исправить предыдущую'} · ⌘/Ctrl + Alt + ←
        </Button>
        <Button
          disabled={correcting || savingReview}
          onClick={() => void skip()}
          variant="ghost"
          size="sm"
        >
          Дальше · ⌘/Ctrl + Alt + →
        </Button>
        <span className="text-caption text-muted-foreground">
          {works.length > 1 ? 'Следующая работа подготовлена' : loading ? 'Готовим следующую…' : ''}
        </span>
      </div>
      {message ? (
        <p role="status" className="py-2 text-small">
          {message}
        </p>
      ) : null}
      {feed.map((item) => (
        <article
          key={item.materialKey}
          ref={(element) => {
            if (element) feedElements.current.set(item.materialKey, element)
            else feedElements.current.delete(item.materialKey)
          }}
          className="my-4 space-y-3 rounded-xl border border-border bg-surface p-4"
        >
          {correcting && editingId === item.reviewId ? (
            <CompletedReviewCard
              reviewId={item.reviewId}
              onClose={closeCorrection}
              onCorrected={(id) => {
                setFeed((items) =>
                  items.map((old) =>
                    old.reviewId === item.reviewId
                      ? { reviewId: id, materialKey: old.materialKey }
                      : old,
                  ),
                )
                setPrevious(id)
              }}
            />
          ) : (
            <>
              {item.movedTo && item.lease ? (
                <ReviewedWorkSnapshot
                  lease={item.lease}
                  mediaClient={mediaClient}
                  annotations={[]}
                  comment=""
                  verdict={`Перенесено в ${item.movedTo}`}
                />
              ) : item.lease && item.draft ? (
                <ReviewedWorkSnapshot
                  lease={item.lease}
                  mediaClient={mediaClient}
                  annotations={item.draft.annotations}
                  comment={item.draft.comment}
                  verdict={writtenReviewVerdict(item.verdict ?? 11).label}
                />
              ) : (
                <CompletedReviewCard
                  reviewId={item.reviewId}
                  readOnly
                  seriesProblemId={problemId}
                  onClose={() => undefined}
                />
              )}
              {!item.movedTo && (
                <Button
                  size="sm"
                  variant="outline"
                  disabled={savingReview || correcting}
                  onClick={() => openCorrection(item.reviewId)}
                >
                  Перепроверить
                </Button>
              )}
            </>
          )}
        </article>
      ))}
      {works.map((work, index) => (
        <div
          key={work.queueId}
          ref={index === 0 ? currentElement : undefined}
          className="scroll-mt-24"
          hidden={index > 0}
          inert={index > 0 || correcting}
        >
          <LoadedReviewWorkspace
            client={client}
            mediaClient={mediaClient}
            principal={principal}
            queueId={work.queueId}
            lease={work.lease}
            inactive={index > 0 || correcting}
            onBusyChange={setSavingReview}
            onCompleted={(response, draft, lease) => finish(work, response, draft, lease)}
            onMoved={(label, entryId, lease) => moved(work, label, entryId, lease)}
          />
        </div>
      ))}
      {!works.length && !correcting ? (
        <PageStatePanel
          state={loading ? 'loading' : 'empty'}
          title="Доступных работ по этой задаче больше нет"
          description="Остальные работы могут проверять другие преподаватели."
          actionLabel="Проверить ещё раз"
          onAction={() => {
            completed.current.clear()
            void fill()
          }}
        />
      ) : null}
      {correcting && editingId && !feed.some((item) => item.reviewId === editingId) ? (
        <section className="space-y-3 py-4">
          <h2 className="text-subtitle font-semibold">Предыдущая проверка</h2>
          <CompletedReviewCard
            reviewId={editingId}
            onClose={closeCorrection}
            onCorrected={(id) => setPrevious(id)}
          />
        </section>
      ) : null}
    </div>
  )
}
