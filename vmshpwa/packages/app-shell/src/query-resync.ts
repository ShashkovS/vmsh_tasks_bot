import type { QueryClient } from '@tanstack/react-query'

const waves = new WeakMap<QueryClient, Promise<void>>()

/** One bounded online/WS refresh; docs/performance/2026-10-08-fixes.md.
 * Cancel older authority reads once, and never recreate queries cleared at logout.
 */
export function resyncActiveQueries(client: QueryClient): Promise<void> {
  const current = waves.get(client)
  if (current) return current
  const queries = client.getQueryCache().findAll({ type: 'active' })
  queries.sort((a, b) => Number(b.queryKey[0] === 'auth') - Number(a.queryKey[0] === 'auth'))
  let cursor = 0
  const worker = async () => {
    for (;;) {
      const query = queries[cursor++]
      if (!query) return
      await client.refetchQueries({ type: 'active', predicate: (candidate) => candidate === query })
    }
  }
  const wave = Promise.all(Array.from({ length: Math.min(4, queries.length) }, worker)).then(
    () => undefined,
  )
  waves.set(client, wave)
  void wave.finally(() => {
    if (waves.get(client) === wave) waves.delete(client)
  })
  return wave
}

export async function waitForQueryResync(client: QueryClient): Promise<void> {
  await waves.get(client)
}
