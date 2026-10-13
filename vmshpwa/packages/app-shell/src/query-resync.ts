import { type Query, type QueryClient } from '@tanstack/react-query'

type Job = { query: Query; due: number; dirty: boolean; replace: boolean }
type Scheduler = {
  queued: Map<Query, Job>
  running: Map<Query, Job>
  promise: Promise<void>
  resolve: () => void
  timer: ReturnType<typeof setTimeout> | undefined
}
type ResyncWave = { promise: Promise<void>; replacing: boolean }
const schedulers = new WeakMap<QueryClient, Scheduler>()
const waves = new WeakMap<QueryClient, ResyncWave>()
const lastStatisticsRead = new WeakMap<Query, number>()
const online = () => typeof navigator === 'undefined' || navigator.onLine !== false
const statistics = (query: Query) => query.meta?.realtimeStatistics === true
const authorized = (query: Query) => query.queryKey[0] === 'auth'

/** Shared four-slot refetch scheduler; scoped-reads-20261013.md.
 * Queued duplicates collapse; an event during a read requests one trailing read.
 * Own mutations and authority checks retain their direct, immediate paths.
 */
export function enqueueQueryRefetches(
  client: QueryClient,
  queries: readonly Query[],
  options: { invalidation?: boolean; delay?: number } = {},
): Promise<void> {
  if (!online()) return Promise.resolve()
  let state = schedulers.get(client)
  if (!state) {
    let resolve = () => undefined as void
    const promise = new Promise<void>((complete) => {
      resolve = complete
    })
    state = { queued: new Map(), running: new Map(), promise, resolve, timer: undefined }
    schedulers.set(client, state)
  }
  const now = Date.now()
  for (const query of queries) {
    if (!query.isActive() || query.isDisabled()) continue
    const running = state.running.get(query)
    if (running) {
      if (options.invalidation) running.dirty = true
      continue
    }
    if (!state.queued.has(query)) {
      state.queued.set(query, {
        query,
        due: now + (authorized(query) ? 0 : (options.delay ?? 0)),
        dirty: false,
        replace: !options.invalidation || authorized(query),
      })
    }
  }
  pump(client, state)
  return state.promise
}

function pump(client: QueryClient, state: Scheduler): void {
  if (state.timer !== undefined) {
    clearTimeout(state.timer)
    state.timer = undefined
  }
  if (!online()) state.queued.clear()
  const cached = client.getQueryCache().getAll()
  for (const [query] of state.queued) {
    if (!cached.includes(query) || !query.isActive() || query.isDisabled())
      state.queued.delete(query)
  }
  const now = Date.now()
  const jobs = [...state.queued.values()].sort(
    (a, b) => Number(authorized(b.query)) - Number(authorized(a.query)),
  )
  for (const job of jobs) {
    if (state.running.size >= 4) break
    const due = statistics(job.query)
      ? Math.max(job.due, (lastStatisticsRead.get(job.query) ?? 0) + 1000)
      : job.due
    if (due > now) continue
    state.queued.delete(job.query)
    state.running.set(job.query, job)
    if (statistics(job.query)) lastStatisticsRead.set(job.query, now)
    // Joining an external fetch also needs a newer read after its old snapshot.
    if (job.query.state.fetchStatus === 'fetching' && !job.replace) job.dirty = true
    void client
      .refetchQueries(
        {
          type: 'active',
          predicate: (candidate) => candidate === job.query,
        },
        { cancelRefetch: job.replace },
      )
      .finally(() => {
        state.running.delete(job.query)
        if (job.dirty && online())
          state.queued.set(job.query, { ...job, due: Date.now(), dirty: false })
        pump(client, state)
      })
  }
  if (state.queued.size && state.running.size < 4) {
    const due = Math.min(
      ...[...state.queued.values()].map((job) =>
        statistics(job.query)
          ? Math.max(job.due, (lastStatisticsRead.get(job.query) ?? 0) + 1000)
          : job.due,
      ),
    )
    state.timer = setTimeout(() => pump(client, state), Math.max(1, due - Date.now()))
  }
  if (!state.queued.size && !state.running.size) {
    if (schedulers.get(client) === state) schedulers.delete(client)
    state.resolve()
  }
}

export function resyncActiveQueries(
  client: QueryClient,
  options: { restart?: boolean } = {},
): Promise<void> {
  if (!online()) return Promise.resolve()
  const current = waves.get(client)
  if (current && (!options.restart || current.replacing)) return current.promise
  const next: ResyncWave = {
    promise: Promise.resolve(),
    replacing: Boolean(current) || Boolean(options.restart),
  }
  const run = async () => {
    if (current || options.restart) {
      const scheduler = schedulers.get(client)
      scheduler?.queued.clear()
      scheduler?.running.forEach((job) => {
        job.dirty = false
      })
      await client.cancelQueries({ type: 'active' })
      if (scheduler) pump(client, scheduler)
      await current?.promise
    }
    next.replacing = false
    await enqueueQueryRefetches(client, client.getQueryCache().findAll({ type: 'active' }))
  }
  next.promise = run()
  waves.set(client, next)
  const complete = () => {
    if (waves.get(client) === next) waves.delete(client)
  }
  void next.promise.then(complete, complete)
  return next.promise
}

export async function waitForQueryResync(client: QueryClient): Promise<void> {
  let current = waves.get(client)
  while (current) {
    await current.promise
    const latest = waves.get(client)
    if (latest === current) return
    current = latest
  }
}
