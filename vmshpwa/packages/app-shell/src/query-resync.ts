import { type Query, type QueryClient } from '@tanstack/react-query'

type ResyncWave = {
  promise: Promise<void>
  queries: Query[]
  cancelled: boolean
  replacing: boolean
}
const waves = new WeakMap<QueryClient, ResyncWave>()
const online = () => typeof navigator === 'undefined' || navigator.onLine !== false

/** One bounded online/WS refresh; docs/performance/2026-10-08-fixes.md.
 * A real offline/online transition replaces older reads once. Ordinary WS and
 * service-ready events join it; see integrated-release-20261008.md.
 */
export function resyncActiveQueries(
  client: QueryClient,
  options: { restart?: boolean } = {},
): Promise<void> {
  if (!online()) return Promise.resolve()
  const current = waves.get(client)
  if (current && (!options.restart || current.replacing)) return current.promise
  const next: ResyncWave = {
    promise: Promise.resolve(),
    queries: [],
    cancelled: false,
    replacing: Boolean(current),
  }
  const run = async () => {
    if (current) {
      current.cancelled = true
      await client.cancelQueries({
        type: 'active',
        predicate: (query) => current.queries.includes(query),
      })
      await current.promise
    }
    next.replacing = false
    if (!online()) return
    next.queries = client.getQueryCache().findAll({ type: 'active' })
    next.queries.sort((a, b) => Number(b.queryKey[0] === 'auth') - Number(a.queryKey[0] === 'auth'))
    let cursor = 0
    const worker = async () => {
      while (!next.cancelled && online()) {
        const query = next.queries[cursor++]
        if (!query) return
        await client.refetchQueries({
          type: 'active',
          predicate: (candidate) => candidate === query,
        })
      }
    }
    await Promise.all(Array.from({ length: Math.min(4, next.queries.length) }, worker))
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
