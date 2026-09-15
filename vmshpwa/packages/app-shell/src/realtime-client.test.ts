import { describe, expect, it, vi } from 'vitest'

import { runtimeBoundaryByAudience, type Audience, type RuntimeConfig } from '@vmsh/contracts'

import {
  DEFAULT_REALTIME_TIMING,
  RealtimeConnection,
  shouldInvalidateRealtimeQuery,
  type RealtimeConnectionState,
  type RealtimeEnvironment,
  type RealtimeQueryOperations,
  type RealtimeSocket,
} from './realtime'

class ManualEnvironment implements RealtimeEnvironment {
  online = true
  visible = true
  now = 0
  #nextHandle = 1
  #listeners = new Set<() => void>()
  #tasks = new Map<number, { at: number; callback: () => void }>()

  isOnline(): boolean {
    return this.online
  }

  isVisible(): boolean {
    return this.visible
  }

  listen(listener: () => void): () => void {
    this.#listeners.add(listener)
    return () => this.#listeners.delete(listener)
  }

  random(): number {
    return 0.5
  }

  setTimeout(callback: () => void, delayMilliseconds: number): number {
    const handle = this.#nextHandle++
    this.#tasks.set(handle, { at: this.now + delayMilliseconds, callback })
    return handle
  }

  clearTimeout(handle: number): void {
    this.#tasks.delete(handle)
  }

  setAvailability({ online = this.online, visible = this.visible } = {}): void {
    this.online = online
    this.visible = visible
    for (const listener of this.#listeners) listener()
  }

  advance(milliseconds: number): void {
    const target = this.now + milliseconds
    for (;;) {
      const next = [...this.#tasks.entries()]
        .filter(([, task]) => task.at <= target)
        .sort((left, right) => left[1].at - right[1].at || left[0] - right[0])[0]
      if (!next) break
      const [handle, task] = next
      this.#tasks.delete(handle)
      this.now = task.at
      task.callback()
    }
    this.now = target
  }
}

class FakeSocket implements RealtimeSocket {
  readyState = 0
  onopen: ((event: unknown) => void) | null = null
  onerror: ((event: unknown) => void) | null = null
  onmessage: ((event: { data: unknown }) => void) | null = null
  onclose: ((event: { code: number }) => void) | null = null
  readonly sent: string[] = []
  readonly closes: Array<{ code?: number; reason?: string }> = []

  open(): void {
    this.readyState = 1
    this.onopen?.({})
  }

  message(payload: unknown): void {
    this.onmessage?.({ data: typeof payload === 'string' ? payload : JSON.stringify(payload) })
  }

  binaryMessage(payload: unknown): void {
    this.onmessage?.({ data: payload })
  }

  serverClose(code: number): void {
    this.readyState = 3
    this.onclose?.({ code })
  }

  send(data: string): void {
    if (this.readyState !== 1) throw new Error('Socket is not open')
    this.sent.push(data)
  }

  close(code?: number, reason?: string): void {
    this.readyState = 3
    this.closes.push({ ...(code === undefined ? {} : { code }), ...(reason ? { reason } : {}) })
  }
}

function runtime(audience: Audience): RuntimeConfig {
  return {
    contractVersion: 1,
    audience,
    ...runtimeBoundaryByAudience[audience],
    instance: 'unit',
    serverTime: '2026-07-27T12:00:00Z',
    requestId: 'request-unit',
    features: { telegram: false, google: false, nats: false, prototype: false },
  }
}

function connected(audience: Audience, cursor = 1) {
  return { type: 'connected', audience, cursor, serverTime: '2026-07-27T12:00:00Z' }
}

function resync(cursor = 1) {
  return {
    type: 'resync-required',
    cursor,
    serverTime: '2026-07-27T12:00:01Z',
    reason: 'reconnect-full-refetch-required',
  }
}

function pong(cursor = 1) {
  return { type: 'pong', cursor, serverTime: '2026-07-27T12:00:02Z' }
}

function invalidate(cursor: number, resources: string[] = ['lesson.current']) {
  return {
    type: 'invalidate',
    audience: 'student',
    cursor,
    serverTime: '2026-07-27T12:00:03Z',
    resources,
    reason: 'unit-proof',
  }
}

function harness(audience: Audience = 'student') {
  const environment = new ManualEnvironment()
  const sockets: FakeSocket[] = []
  const urls: string[] = []
  const states: RealtimeConnectionState[] = []
  const refetchActiveQueries = vi.fn(() => Promise.resolve())
  const invalidateActiveQueries = vi.fn<RealtimeQueryOperations['invalidateActiveQueries']>(() =>
    Promise.resolve(),
  )
  const refetchAuthentication = vi.fn<RealtimeQueryOperations['refetchAuthentication']>(() =>
    Promise.resolve('unauthenticated'),
  )
  const queries: RealtimeQueryOperations = {
    refetchActiveQueries,
    invalidateActiveQueries,
    refetchAuthentication,
  }
  const connection = new RealtimeConnection({
    audience,
    runtime: runtime(audience),
    environment,
    queries,
    socketFactory: (url) => {
      urls.push(url)
      const socket = new FakeSocket()
      sockets.push(socket)
      return socket
    },
    onStateChange: (state) => states.push(state),
  })
  return {
    connection,
    environment,
    queries,
    querySpies: { invalidateActiveQueries, refetchActiveQueries, refetchAuthentication },
    sockets,
    states,
    urls,
  }
}

async function flushPromises(): Promise<void> {
  await Promise.resolve()
  await Promise.resolve()
}

describe('RealtimeConnection', () => {
  it.each<Audience>(['student', 'family', 'staff'])(
    'uses the exact same-origin %s path without credentials in the URL',
    (audience) => {
      const { connection, sockets, urls } = harness(audience)
      connection.start()

      expect(sockets).toHaveLength(1)
      const url = new URL(urls[0] ?? '')
      expect(url.pathname).toBe(runtimeBoundaryByAudience[audience].websocketPath)
      expect(url.origin).toBe('ws://localhost:3000')
      expect(url.search).toBe('')
      expect(url.username).toBe('')
      expect(url.password).toBe('')
    },
  )

  it('accepts the first handshake and keeps a bounded JSON ping/pong heartbeat', () => {
    const { connection, environment, sockets, states } = harness()
    connection.start()
    const socket = sockets[0]!
    socket.open()
    socket.message(connected('student', 4))

    expect(states.at(-1)).toEqual({ status: 'ready', cursor: 4, reconnected: false })
    environment.advance(DEFAULT_REALTIME_TIMING.heartbeatIntervalMilliseconds)
    expect(socket.sent).toEqual([JSON.stringify({ type: 'ping' })])
    socket.message(pong(5))
    environment.advance(DEFAULT_REALTIME_TIMING.heartbeatTimeoutMilliseconds)
    expect(sockets).toHaveLength(1)
    expect(states.at(-1)).toEqual({ status: 'ready', cursor: 5, reconnected: false })
  })

  it('coalesces validated invalidations before refetching active Query data', async () => {
    const { connection, environment, querySpies, sockets } = harness()
    connection.start()
    const socket = sockets[0]!
    socket.open()
    socket.message(connected('student'))
    socket.message(invalidate(2))
    socket.message(invalidate(3, ['news']))

    environment.advance(DEFAULT_REALTIME_TIMING.invalidationCoalesceMilliseconds - 1)
    expect(querySpies.invalidateActiveQueries).not.toHaveBeenCalled()
    environment.advance(1)
    await flushPromises()
    expect(querySpies.invalidateActiveQueries).toHaveBeenCalledTimes(1)
    expect(querySpies.invalidateActiveQueries).toHaveBeenCalledWith(['lesson.current', 'news'])
  })

  it('routes ordinary invalidations by resource while preserving conservative queries', () => {
    expect(shouldInvalidateRealtimeQuery(undefined, ['review-queue'])).toBe(true)
    expect(
      shouldInvalidateRealtimeQuery({ realtimeResources: ['review-queue'] }, ['review-queue']),
    ).toBe(true)
    expect(
      shouldInvalidateRealtimeQuery({ realtimeResources: ['review-lease'] }, ['review-queue']),
    ).toBe(false)
    expect(shouldInvalidateRealtimeQuery({ realtimeResources: [] }, ['review-queue'])).toBe(false)
  })

  it('fails closed on malformed frames and reconnects with only the in-memory cursor', async () => {
    const { connection, environment, querySpies, sockets, states, urls } = harness()
    connection.start()
    sockets[0]!.open()
    sockets[0]!.message(connected('student', 7))
    sockets[0]!.message('{malformed')

    expect(sockets[0]!.closes).toEqual([{ code: 1002, reason: 'Realtime protocol error' }])
    expect(states.at(-1)).toMatchObject({ status: 'degraded', reason: 'protocol' })
    environment.advance(DEFAULT_REALTIME_TIMING.reconnectBaseMilliseconds)
    expect(sockets).toHaveLength(2)
    const reconnectUrl = new URL(urls[1] ?? '')
    expect(reconnectUrl.searchParams.get('cursor')).toBe('7')
    expect([...reconnectUrl.searchParams]).toEqual([['cursor', '7']])

    sockets[1]!.open()
    sockets[1]!.message(resync(2))
    expect(states.at(-1)).toEqual({ status: 'resyncing', cursor: 7 })
    await flushPromises()
    expect(querySpies.refetchActiveQueries).toHaveBeenCalledTimes(1)
    expect(states.at(-1)).toEqual({ status: 'ready', cursor: 7, reconnected: true })
  })

  it('does not become ready until the reconnect authority refetch finishes', async () => {
    let releaseRefetch: (() => void) | undefined
    const pendingRefetch = new Promise<void>((resolve) => {
      releaseRefetch = resolve
    })
    const { connection, environment, querySpies, sockets, states } = harness()
    querySpies.refetchActiveQueries.mockReturnValueOnce(pendingRefetch)
    connection.start()
    sockets[0]!.open()
    sockets[0]!.message(connected('student', 1))
    sockets[0]!.serverClose(1012)
    environment.advance(DEFAULT_REALTIME_TIMING.reconnectBaseMilliseconds)
    sockets[1]!.open()
    sockets[1]!.message(resync(1))

    expect(states.at(-1)).toEqual({ status: 'resyncing', cursor: 1 })
    releaseRefetch?.()
    await flushPromises()
    expect(states.at(-1)).toEqual({ status: 'ready', cursor: 1, reconnected: true })
  })

  it('treats wrong-audience and binary frames as protocol failures', () => {
    const wrongAudience = harness()
    wrongAudience.connection.start()
    wrongAudience.sockets[0]!.open()
    wrongAudience.sockets[0]!.message(connected('family'))
    expect(wrongAudience.sockets[0]!.closes[0]?.code).toBe(1002)

    const binary = harness()
    binary.connection.start()
    binary.sockets[0]!.open()
    binary.sockets[0]!.binaryMessage(new Uint8Array([1, 2, 3]))
    expect(binary.sockets[0]!.closes[0]?.code).toBe(1002)
  })

  it('times out a missing pong and reconnects with exponential jitter', () => {
    const { connection, environment, sockets, states } = harness()
    connection.start()
    sockets[0]!.open()
    sockets[0]!.message(connected('student'))
    environment.advance(DEFAULT_REALTIME_TIMING.heartbeatIntervalMilliseconds)
    environment.advance(DEFAULT_REALTIME_TIMING.heartbeatTimeoutMilliseconds)

    expect(states.at(-1)).toMatchObject({ status: 'degraded', reason: 'heartbeat' })
    environment.advance(DEFAULT_REALTIME_TIMING.reconnectBaseMilliseconds)
    expect(sockets).toHaveLength(2)
  })

  it('checks HTTP authority once after policy close and never enters a reconnect loop', async () => {
    const { connection, environment, querySpies, sockets, states } = harness()
    connection.start()
    sockets[0]!.open()
    sockets[0]!.message(connected('student'))
    sockets[0]!.serverClose(1008)
    await flushPromises()

    expect(states.at(-1)).toEqual({ status: 'checking-authority' })
    expect(querySpies.refetchAuthentication).toHaveBeenCalledTimes(1)
    environment.advance(10 * DEFAULT_REALTIME_TIMING.reconnectMaximumMilliseconds)
    expect(sockets).toHaveLength(1)
  })

  it('reconnects only when HTTP authority positively confirms authentication after policy close', async () => {
    const { connection, environment, querySpies, sockets } = harness()
    querySpies.refetchAuthentication.mockResolvedValueOnce('authenticated')
    connection.start()
    sockets[0]!.open()
    sockets[0]!.message(connected('student'))
    sockets[0]!.serverClose(1008)
    await flushPromises()

    environment.advance(DEFAULT_REALTIME_TIMING.reconnectBaseMilliseconds)
    expect(sockets).toHaveLength(2)
  })

  it('treats an ambiguous clean close as authority-sensitive before reconnecting', async () => {
    const { connection, environment, querySpies, sockets, states } = harness()
    querySpies.refetchAuthentication.mockResolvedValueOnce('authenticated')
    connection.start()
    sockets[0]!.open()
    sockets[0]!.message(connected('student'))
    sockets[0]!.serverClose(1000)
    await flushPromises()

    expect(querySpies.refetchAuthentication).toHaveBeenCalledTimes(1)
    expect(states.at(-1)).toMatchObject({ status: 'degraded', reason: 'transport' })
    environment.advance(DEFAULT_REALTIME_TIMING.reconnectBaseMilliseconds)
    expect(sockets).toHaveLength(2)
  })

  it('retries a transient authority failure and recovers after a clean close', async () => {
    const { connection, environment, querySpies, sockets, states } = harness()
    querySpies.refetchAuthentication
      .mockResolvedValueOnce('unavailable')
      .mockResolvedValueOnce('authenticated')
    connection.start()
    sockets[0]!.open()
    sockets[0]!.message(connected('student'))
    sockets[0]!.serverClose(1000)
    await flushPromises()

    expect(querySpies.refetchAuthentication).toHaveBeenCalledTimes(1)
    expect(states.at(-1)).toEqual({
      status: 'degraded',
      reason: 'transport',
      retryInMilliseconds: DEFAULT_REALTIME_TIMING.reconnectBaseMilliseconds,
    })
    environment.advance(DEFAULT_REALTIME_TIMING.reconnectBaseMilliseconds)
    await flushPromises()
    expect(querySpies.refetchAuthentication).toHaveBeenCalledTimes(2)
    expect(sockets).toHaveLength(1)

    environment.advance(DEFAULT_REALTIME_TIMING.reconnectBaseMilliseconds * 2)
    expect(sockets).toHaveLength(2)
  })

  it('bounds a WebSocket that never leaves CONNECTING and retries', () => {
    const { connection, environment, sockets, states } = harness()
    connection.start()
    expect(sockets[0]!.readyState).toBe(0)

    environment.advance(DEFAULT_REALTIME_TIMING.handshakeTimeoutMilliseconds)
    expect(sockets[0]!.closes).toEqual([{ code: 1000, reason: 'Reconnect' }])
    expect(states.at(-1)).toMatchObject({ status: 'degraded', reason: 'transport' })
    environment.advance(DEFAULT_REALTIME_TIMING.reconnectBaseMilliseconds)
    expect(sockets).toHaveLength(2)
  })

  it('pauses reconnect while offline or hidden and resumes when usable', () => {
    const offline = harness()
    offline.environment.setAvailability({ online: false })
    offline.connection.start()
    expect(offline.sockets).toHaveLength(0)
    expect(offline.states.at(-1)).toEqual({ status: 'waiting', reason: 'offline' })
    offline.environment.setAvailability({ online: true })
    expect(offline.sockets).toHaveLength(1)

    offline.sockets[0]!.open()
    offline.sockets[0]!.message(connected('student'))
    offline.environment.setAvailability({ visible: false })
    offline.sockets[0]!.serverClose(1012)
    expect(offline.states.at(-1)).toEqual({ status: 'waiting', reason: 'hidden' })
    offline.environment.setAvailability({ visible: true })
    expect(offline.sockets).toHaveLength(2)
  })

  it('cleans up a StrictMode-shaped first mount without a duplicate live transport', () => {
    const first = harness()
    first.connection.start()
    first.connection.stop()
    first.environment.advance(10 * DEFAULT_REALTIME_TIMING.reconnectMaximumMilliseconds)
    expect(first.sockets).toHaveLength(1)
    expect(first.sockets[0]!.closes).toEqual([{ code: 1000, reason: 'Realtime provider stopped' }])

    const second = harness()
    second.connection.start()
    expect(second.sockets).toHaveLength(1)
    expect(second.sockets[0]!.closes).toEqual([])
  })
})
