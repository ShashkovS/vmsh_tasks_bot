import { useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useCallback, useEffect, useRef, useState } from 'react'
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
import { LoadedReviewWorkspace } from './review-workspace-page'
import { CompletedReviewCard } from './review-history-page'
import { lastCompletedReview } from './last-completed-review'
import { allReviewItems, seriesCandidates } from './review-series-model'
import { describeReviewError } from './review-errors'

type PreparedWork = { queueId: string; lease: ReviewLease }

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
  const [savingReview, setSavingReview] = useState(false)
  const skipBusy = useRef(false)

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

  const finish = (work: PreparedWork, response: CompleteReviewResponse) => {
    setSavingReview(false)
    completed.current.add(work.lease.logicalCaseId)
    setPrevious(response.review.reviewId)
    owned.current = owned.current.filter((item) => item.queueId !== work.queueId)
    setWorks(owned.current)
    window.scrollTo({ top: 0, behavior: 'instant' })
  }
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
        setCorrecting((value) => !value)
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
      <div className="sticky top-0 z-10 flex flex-wrap items-center gap-2 border-b border-border bg-background py-2">
        <Button render={<Link to="/review" />} variant="outline" size="sm">
          К списку задач
        </Button>
        <Button
          disabled={!previous || savingReview}
          onClick={() => setCorrecting((value) => !value)}
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
      {works.map((work, index) => (
        <div key={work.queueId} hidden={index > 0 || correcting} inert={index > 0 || correcting}>
          <LoadedReviewWorkspace
            client={client}
            mediaClient={mediaClient}
            principal={principal}
            queueId={work.queueId}
            lease={work.lease}
            inactive={index > 0 || correcting}
            onBusyChange={setSavingReview}
            onCompleted={(response) => finish(work, response)}
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
      {correcting && previous ? (
        <section className="space-y-3 py-4">
          <h2 className="text-subtitle font-semibold">Предыдущая проверка</h2>
          <CompletedReviewCard
            reviewId={previous}
            onClose={() => {
              setPrevious(lastCompletedReview(namespace, principal.accountId) ?? previous)
              setCorrecting(false)
            }}
          />
        </section>
      ) : null}
    </div>
  )
}
