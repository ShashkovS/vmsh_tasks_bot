import { QueryClient, QueryObserver } from '@tanstack/react-query'
import { expect, it, vi } from 'vitest'
import { resyncActiveQueries, waitForQueryResync } from './query-resync'
import { createAppQueryClient } from './providers'

it('skips a late recovery-ready event while offline and preserves the next online resync', async () => {
  const online = vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false)
  const client = createAppQueryClient()
  const read = vi.fn(() => Promise.resolve('fresh'))
  const unsubscribe = new QueryObserver(client, {
    queryKey: ['auth', 'student', 'me'],
    queryFn: read,
    networkMode: 'always',
    initialData: 'cached',
    staleTime: Infinity,
  }).subscribe(() => undefined)
  try {
    await resyncActiveQueries(client)
    expect(read).not.toHaveBeenCalled()
    expect(client.getQueryData(['auth', 'student', 'me'])).toBe('cached')
    online.mockReturnValue(true)
    await resyncActiveQueries(client)
    expect(read).toHaveBeenCalledTimes(1)
    expect(client.getQueryData(['auth', 'student', 'me'])).toBe('fresh')
  } finally {
    unsubscribe()
    client.clear()
    online.mockRestore()
  }
})

it('coalesces online/WS refreshes, bounds concurrency and keeps invalidations newer', async () => {
  const client = createAppQueryClient()
  let running = 0
  let peak = 0
  const releases: (() => void)[] = []
  const read = vi.fn(
    () =>
      new Promise<string>((resolve) => {
        running++
        peak = Math.max(peak, running)
        releases.push(() => {
          running--
          resolve('fresh')
        })
      }),
  )
  const unsubscribes = Array.from({ length: 9 }, (_, index) => {
    const observer = new QueryObserver(client, {
      queryKey: ['resync', index],
      queryFn: read,
      initialData: 'old',
      staleTime: Infinity,
    })
    return observer.subscribe(() => undefined)
  })
  await client.invalidateQueries({ refetchType: 'none' })
  const online = resyncActiveQueries(client)
  const websocket = resyncActiveQueries(client)
  client.getQueryCache().onOnline()
  expect(websocket).toBe(online)
  expect(read).toHaveBeenCalledTimes(4)
  let invalidationStarted = false
  const invalidation = waitForQueryResync(client).then(() => {
    invalidationStarted = true
  })
  for (let batch = 0; batch < 3; batch++) {
    releases.splice(0).forEach((release) => release())
    await vi.waitFor(() => expect(read).toHaveBeenCalledTimes(Math.min(9, (batch + 2) * 4)))
    if (batch < 2) expect(invalidationStarted).toBe(false)
  }
  await online
  await invalidation
  expect(peak).toBe(4)
  expect(invalidationStarted).toBe(true)
  expect(client.getQueryData(['resync', 8])).toBe('fresh')
  unsubscribes.forEach((unsubscribe) => unsubscribe())
  client.clear()
})

it('replaces reads from before offline once and retains four concurrent requests', async () => {
  const client = createAppQueryClient()
  const pending: (() => void)[] = []
  let running = 0
  let peak = 0
  const read = vi.fn(
    ({ signal }: { signal: AbortSignal }) =>
      new Promise<string>((resolve, reject) => {
        running++
        peak = Math.max(peak, running)
        signal.addEventListener(
          'abort',
          () => {
            running--
            reject(new DOMException('Cancelled', 'AbortError'))
          },
          { once: true },
        )
        pending.push(() => {
          if (signal.aborted) return
          running--
          resolve('fresh')
        })
      }),
  )
  const unsubscribes = Array.from({ length: 6 }, (_, index) =>
    new QueryObserver(client, {
      queryKey: ['restart', index],
      queryFn: read,
      initialData: 'old',
      staleTime: Infinity,
    }).subscribe(() => undefined),
  )
  const earlier = resyncActiveQueries(client)
  expect(read).toHaveBeenCalledTimes(4)
  let invalidationReady = false
  const invalidation = waitForQueryResync(client).then(() => {
    invalidationReady = true
  })
  const reconnect = resyncActiveQueries(client, { restart: true })
  expect(resyncActiveQueries(client, { restart: true })).toBe(reconnect)
  await vi.waitFor(() => expect(read).toHaveBeenCalledTimes(8))
  expect(invalidationReady).toBe(false)
  pending.splice(0).forEach((release) => release())
  await vi.waitFor(() => expect(read).toHaveBeenCalledTimes(10))
  pending.splice(0).forEach((release) => release())
  await Promise.all([earlier, reconnect, invalidation])
  expect(invalidationReady).toBe(true)
  expect(peak).toBe(4)
  for (let index = 0; index < 6; index++)
    expect(client.getQueryData(['restart', index])).toBe('fresh')
  unsubscribes.forEach((unsubscribe) => unsubscribe())
  client.clear()
})

it('does not recreate queued queries after logout or refresh disabled queries', async () => {
  const client = new QueryClient()
  const releases: (() => void)[] = []
  const read = vi.fn(() => new Promise<string>((resolve) => releases.push(() => resolve('fresh'))))
  const unsubscribes = Array.from({ length: 6 }, (_, index) =>
    new QueryObserver(client, {
      queryKey: ['logout', index],
      queryFn: read,
      initialData: 'old',
      staleTime: Infinity,
      enabled: index !== 0,
    }).subscribe(() => undefined),
  )
  const wave = resyncActiveQueries(client)
  expect(read).toHaveBeenCalledTimes(4)
  client.clear()
  releases.forEach((release) => release())
  await wave
  expect(read).toHaveBeenCalledTimes(4)
  expect(client.getQueryCache().getAll()).toHaveLength(0)
  unsubscribes.forEach((unsubscribe) => unsubscribe())
})
