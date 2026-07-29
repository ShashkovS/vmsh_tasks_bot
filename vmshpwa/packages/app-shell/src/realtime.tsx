import { useQueryClient } from '@tanstack/react-query'
import {
  authQueryKeys,
  parseRuntimeConfigForAudience,
  realtimeEventSchema,
  type Audience,
  type RealtimeEvent,
  type RuntimeConfig,
} from '@vmsh/contracts'
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'

import { useAuthentication } from './auth-context'

const SOCKET_OPEN = 1
const CLOSE_NORMAL = 1000
const CLOSE_PROTOCOL_ERROR = 1002
const CLOSE_POLICY_VIOLATION = 1008

export const DEFAULT_REALTIME_TIMING = {
  handshakeTimeoutMilliseconds: 10_000,
  heartbeatIntervalMilliseconds: 20_000,
  heartbeatTimeoutMilliseconds: 10_000,
  invalidationCoalesceMilliseconds: 50,
  reconnectBaseMilliseconds: 500,
  reconnectMaximumMilliseconds: 30_000,
} as const

export interface RealtimeTiming {
  handshakeTimeoutMilliseconds: number
  heartbeatIntervalMilliseconds: number
  heartbeatTimeoutMilliseconds: number
  invalidationCoalesceMilliseconds: number
  reconnectBaseMilliseconds: number
  reconnectMaximumMilliseconds: number
}

export type RealtimeConnectionState =
  | { status: 'idle' }
  | { status: 'waiting'; reason: 'offline' | 'hidden' }
  | { status: 'connecting'; attempt: number; reconnect: boolean }
  | { status: 'resyncing'; cursor: number }
  | { status: 'ready'; cursor: number; reconnected: boolean }
  | {
      status: 'degraded'
      reason: 'heartbeat' | 'protocol' | 'transport'
      retryInMilliseconds: number
    }
  | { status: 'checking-authority' }

export interface RealtimeConnectionValue {
  audience: Audience
  state: RealtimeConnectionState
}

interface SocketMessageEvent {
  data: unknown
}
interface SocketCloseEvent {
  code: number
}

export interface RealtimeSocket {
  readonly readyState: number
  onopen: ((event: unknown) => void) | null
  onerror: ((event: unknown) => void) | null
  onmessage: ((event: SocketMessageEvent) => void) | null
  onclose: ((event: SocketCloseEvent) => void) | null
  send(data: string): void
  close(code?: number, reason?: string): void
}

export type RealtimeSocketFactory = (url: string) => RealtimeSocket

export interface RealtimeEnvironment {
  isOnline(): boolean
  isVisible(): boolean
  listen(onAvailabilityChange: () => void): () => void
  random(): number
  setTimeout(callback: () => void, delayMilliseconds: number): number
  clearTimeout(handle: number): void
}

export interface RealtimeQueryOperations {
  refetchActiveQueries(): Promise<void>
  invalidateActiveQueries(resources: readonly string[]): Promise<void>
  refetchAuthentication(): Promise<'authenticated' | 'unauthenticated' | 'unavailable'>
}

export interface RealtimeConnectionOptions {
  audience: Audience
  runtime: RuntimeConfig
  queries: RealtimeQueryOperations
  onStateChange: (state: RealtimeConnectionState) => void
  socketFactory?: RealtimeSocketFactory
  environment?: RealtimeEnvironment
  timing?: Partial<RealtimeTiming>
}

/**
 * Unlabelled queries retain the conservative Phase-1 behaviour. Queries that
 * opt into resource routing are invalidated only by matching live resources;
 * an empty list deliberately means reconnect-only refetching.
 */
export function shouldInvalidateRealtimeQuery(
  meta: Record<string, unknown> | undefined,
  resources: readonly string[],
): boolean {
  const configured = meta?.realtimeResources
  if (!Array.isArray(configured) || !configured.every((resource) => typeof resource === 'string')) {
    return true
  }
  const changed = new Set(resources)
  return configured.some((resource) => changed.has(resource))
}

const RealtimeConnectionContext = createContext<RealtimeConnectionValue | null>(null)

function browserSocketFactory(url: string): RealtimeSocket {
  return new window.WebSocket(url) as unknown as RealtimeSocket
}

function browserEnvironment(): RealtimeEnvironment {
  return {
    isOnline: () => window.navigator.onLine,
    isVisible: () => document.visibilityState !== 'hidden',
    listen: (onAvailabilityChange) => {
      window.addEventListener('online', onAvailabilityChange)
      window.addEventListener('offline', onAvailabilityChange)
      document.addEventListener('visibilitychange', onAvailabilityChange)
      return () => {
        window.removeEventListener('online', onAvailabilityChange)
        window.removeEventListener('offline', onAvailabilityChange)
        document.removeEventListener('visibilitychange', onAvailabilityChange)
      }
    },
    random: () => Math.random(),
    setTimeout: (callback, delayMilliseconds) => window.setTimeout(callback, delayMilliseconds),
    clearTimeout: (handle) => window.clearTimeout(handle),
  }
}

/**
 * Memory-only realtime transport for Phase 1.
 *
 * The URL contains only the server cursor; authentication remains in the
 * audience-scoped HttpOnly cookie. Every frame is parsed by the shared Zod
 * contract before it can invalidate Query data. See Phase 1 in
 * `dev/development-plan/05-phase-1-auth.md` and `realtime-client.test.ts`.
 */
export class RealtimeConnection {
  readonly #audience: Audience
  readonly #websocketPath: string
  readonly #queries: RealtimeQueryOperations
  readonly #onStateChange: (state: RealtimeConnectionState) => void
  readonly #socketFactory: RealtimeSocketFactory
  readonly #environment: RealtimeEnvironment
  readonly #timing: RealtimeTiming

  #running = false
  #policyBlocked = false
  #hasAttemptedConnection = false
  #socket: RealtimeSocket | null = null
  #socketGeneration = 0
  #cursor: number | null = null
  #currentReadyWasReconnect = false
  #retryCount = 0
  #unsubscribeAvailability: (() => void) | null = null
  #retryTimer: number | null = null
  #handshakeTimer: number | null = null
  #heartbeatTimer: number | null = null
  #pongTimer: number | null = null
  #invalidationTimer: number | null = null
  #invalidationInFlight = false
  #invalidationPending = false
  readonly #invalidationResources = new Set<string>()
  #authorityCheckInFlight = false

  constructor(options: RealtimeConnectionOptions) {
    const runtime = parseRuntimeConfigForAudience(options.audience, options.runtime)
    this.#audience = options.audience
    this.#websocketPath = runtime.websocketPath
    this.#queries = options.queries
    this.#onStateChange = options.onStateChange
    this.#socketFactory = options.socketFactory ?? browserSocketFactory
    this.#environment = options.environment ?? browserEnvironment()
    this.#timing = { ...DEFAULT_REALTIME_TIMING, ...options.timing }
  }

  start(): void {
    if (this.#running) return
    this.#running = true
    this.#policyBlocked = false
    this.#unsubscribeAvailability = this.#environment.listen(() => this.#availabilityChanged())
    this.#ensureConnection()
  }

  stop(): void {
    if (!this.#running) return
    this.#running = false
    this.#socketGeneration += 1
    this.#unsubscribeAvailability?.()
    this.#unsubscribeAvailability = null
    this.#clearAllTimers()
    this.#detachAndCloseSocket(CLOSE_NORMAL, 'Realtime provider stopped')
  }

  #availabilityChanged(): void {
    if (!this.#running) return
    if (this.#policyBlocked) {
      if (!this.#environment.isOnline()) {
        this.#cancelRetry()
        this.#onStateChange({ status: 'waiting', reason: 'offline' })
        return
      }
      if (!this.#environment.isVisible()) {
        this.#cancelRetry()
        this.#onStateChange({ status: 'waiting', reason: 'hidden' })
        return
      }
      if (this.#retryTimer === null && !this.#authorityCheckInFlight) {
        void this.#checkAuthority()
      }
      return
    }
    if (!this.#environment.isOnline()) {
      this.#cancelRetry()
      this.#detachAndCloseSocket(CLOSE_NORMAL, 'Browser is offline')
      this.#onStateChange({ status: 'waiting', reason: 'offline' })
      return
    }
    if (!this.#environment.isVisible() && this.#socket === null) {
      this.#cancelRetry()
      this.#onStateChange({ status: 'waiting', reason: 'hidden' })
      return
    }
    if (this.#socket === null && this.#retryTimer === null) this.#ensureConnection()
  }

  #ensureConnection(): void {
    if (!this.#running || this.#policyBlocked || this.#socket !== null) return
    if (!this.#environment.isOnline()) {
      this.#onStateChange({ status: 'waiting', reason: 'offline' })
      return
    }
    if (!this.#environment.isVisible()) {
      this.#onStateChange({ status: 'waiting', reason: 'hidden' })
      return
    }
    this.#openSocket()
  }

  #openSocket(): void {
    const reconnect = this.#hasAttemptedConnection
    const attempt = this.#retryCount + 1
    const url = new URL(this.#websocketPath, window.location.origin)
    url.protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    if (reconnect) url.searchParams.set('cursor', String(this.#cursor ?? 0))

    this.#onStateChange({ status: 'connecting', attempt, reconnect })
    this.#hasAttemptedConnection = true
    const generation = ++this.#socketGeneration

    let socket: RealtimeSocket
    try {
      socket = this.#socketFactory(url.toString())
    } catch {
      this.#scheduleReconnect('transport')
      return
    }
    this.#socket = socket
    socket.onopen = () => undefined
    socket.onerror = () => {
      if (this.#isCurrent(socket, generation)) {
        this.#failConnection(socket, generation, 'transport', CLOSE_NORMAL)
      }
    }
    socket.onclose = (event) => {
      if (!this.#isCurrent(socket, generation)) return
      this.#socket = null
      this.#clearConnectionTimers()
      if (!this.#running) return
      if (event.code === CLOSE_POLICY_VIOLATION || event.code === CLOSE_NORMAL) {
        // Reverse proxies and browser automation layers do not always preserve
        // a server's policy close code. A clean close is therefore ambiguous:
        // verify HTTP authority once before reconnecting. Ordinary abnormal
        // transport failures keep the bounded reconnect path below.
        this.#handleAuthoritySensitiveClose()
        return
      }
      this.#scheduleReconnect('transport')
    }
    socket.onmessage = (message) => {
      if (this.#isCurrent(socket, generation)) {
        this.#handleMessage(socket, generation, reconnect, message.data)
      }
    }
    // Bound both CONNECTING and the server handshake. Some browser/network
    // failures produce neither open, error nor close, so arming this only from
    // `onopen` would leave the product in `connecting` forever.
    this.#armHandshakeTimeout(socket, generation)
  }

  #armHandshakeTimeout(socket: RealtimeSocket, generation: number): void {
    this.#clearTimer('handshake')
    this.#handshakeTimer = this.#environment.setTimeout(() => {
      if (this.#isCurrent(socket, generation)) {
        this.#failConnection(socket, generation, 'transport', CLOSE_NORMAL)
      }
    }, this.#timing.handshakeTimeoutMilliseconds)
  }

  #handleMessage(
    socket: RealtimeSocket,
    generation: number,
    reconnect: boolean,
    rawData: unknown,
  ): void {
    if (typeof rawData !== 'string') {
      this.#failConnection(socket, generation, 'protocol', CLOSE_PROTOCOL_ERROR)
      return
    }

    let rawEvent: unknown
    try {
      rawEvent = JSON.parse(rawData)
    } catch {
      this.#failConnection(socket, generation, 'protocol', CLOSE_PROTOCOL_ERROR)
      return
    }
    const parsed = realtimeEventSchema.safeParse(rawEvent)
    if (!parsed.success || ('audience' in parsed.data && parsed.data.audience !== this.#audience)) {
      this.#failConnection(socket, generation, 'protocol', CLOSE_PROTOCOL_ERROR)
      return
    }

    const event = parsed.data
    this.#cursor = Math.max(this.#cursor ?? 0, event.cursor)
    if (this.#handshakeTimer !== null) {
      const expectedHandshake = reconnect ? 'resync-required' : 'connected'
      if (event.type !== expectedHandshake) {
        this.#failConnection(socket, generation, 'protocol', CLOSE_PROTOCOL_ERROR)
        return
      }
      this.#clearTimer('handshake')
      if (event.type === 'resync-required') {
        this.#onStateChange({ status: 'resyncing', cursor: this.#cursor })
        void this.#completeReconnect(socket, generation)
      } else {
        this.#becomeReady(socket, generation, false)
      }
      return
    }

    this.#handleEstablishedEvent(socket, generation, event)
  }

  async #completeReconnect(socket: RealtimeSocket, generation: number): Promise<void> {
    try {
      // Reconnect cursor is deliberately not treated as a durable log. The
      // authoritative read models come from HTTP/SQLite before readiness.
      await this.#queries.refetchActiveQueries()
    } catch {
      // TanStack normally resolves refetchQueries even when one query fails,
      // but an injected/custom query controller may reject. Stay fail-closed.
      if (this.#isCurrent(socket, generation)) {
        this.#failConnection(socket, generation, 'transport', CLOSE_NORMAL)
      }
      return
    }
    if (this.#isCurrent(socket, generation)) this.#becomeReady(socket, generation, true)
  }

  #handleEstablishedEvent(socket: RealtimeSocket, generation: number, event: RealtimeEvent): void {
    switch (event.type) {
      case 'pong':
        if (this.#pongTimer === null) {
          this.#failConnection(socket, generation, 'protocol', CLOSE_PROTOCOL_ERROR)
          return
        }
        this.#clearTimer('pong')
        this.#retryCount = 0
        this.#publishReadyState()
        this.#scheduleHeartbeat(socket, generation)
        return
      case 'invalidate':
        this.#publishReadyState()
        this.#scheduleInvalidation(event.resources)
        return
      case 'connected':
      case 'resync-required':
      case 'error':
        this.#failConnection(socket, generation, 'protocol', CLOSE_PROTOCOL_ERROR)
    }
  }

  #becomeReady(socket: RealtimeSocket, generation: number, reconnected: boolean): void {
    if (!this.#isCurrent(socket, generation)) return
    this.#currentReadyWasReconnect = reconnected
    this.#publishReadyState()
    this.#scheduleHeartbeat(socket, generation)
  }

  #publishReadyState(): void {
    this.#onStateChange({
      status: 'ready',
      cursor: this.#cursor ?? 0,
      reconnected: this.#currentReadyWasReconnect,
    })
  }

  #scheduleHeartbeat(socket: RealtimeSocket, generation: number): void {
    this.#clearTimer('heartbeat')
    this.#heartbeatTimer = this.#environment.setTimeout(() => {
      if (!this.#isCurrent(socket, generation) || socket.readyState !== SOCKET_OPEN) return
      try {
        socket.send(JSON.stringify({ type: 'ping' }))
      } catch {
        this.#failConnection(socket, generation, 'transport', CLOSE_NORMAL)
        return
      }
      this.#pongTimer = this.#environment.setTimeout(() => {
        if (this.#isCurrent(socket, generation)) {
          this.#failConnection(socket, generation, 'heartbeat', CLOSE_NORMAL)
        }
      }, this.#timing.heartbeatTimeoutMilliseconds)
    }, this.#timing.heartbeatIntervalMilliseconds)
  }

  #scheduleInvalidation(resources: readonly string[] = []): void {
    for (const resource of resources) this.#invalidationResources.add(resource)
    if (this.#invalidationTimer !== null || this.#invalidationInFlight) {
      this.#invalidationPending = true
      return
    }
    this.#invalidationTimer = this.#environment.setTimeout(() => {
      this.#invalidationTimer = null
      if (!this.#running) return
      const pendingResources = [...this.#invalidationResources]
      this.#invalidationResources.clear()
      this.#invalidationInFlight = true
      void this.#queries
        .invalidateActiveQueries(pendingResources)
        .catch(() => undefined)
        .finally(() => {
          this.#invalidationInFlight = false
          if (!this.#running) return
          if (this.#invalidationPending) {
            this.#invalidationPending = false
            this.#scheduleInvalidation()
          }
        })
    }, this.#timing.invalidationCoalesceMilliseconds)
  }

  #failConnection(
    socket: RealtimeSocket,
    generation: number,
    reason: 'heartbeat' | 'protocol' | 'transport',
    closeCode: number,
  ): void {
    if (!this.#isCurrent(socket, generation)) return
    this.#socket = null
    this.#socketGeneration += 1
    this.#clearConnectionTimers()
    this.#detachSocket(socket)
    try {
      socket.close(closeCode, reason === 'protocol' ? 'Realtime protocol error' : 'Reconnect')
    } catch {
      // The socket is already detached; reconnect remains bounded below.
    }
    this.#scheduleReconnect(reason)
  }

  #scheduleReconnect(reason: 'heartbeat' | 'protocol' | 'transport'): void {
    if (!this.#running || this.#policyBlocked || this.#retryTimer !== null) return
    if (!this.#environment.isOnline()) {
      this.#onStateChange({ status: 'waiting', reason: 'offline' })
      return
    }
    if (!this.#environment.isVisible()) {
      this.#onStateChange({ status: 'waiting', reason: 'hidden' })
      return
    }

    const retryInMilliseconds = this.#nextRetryDelay()
    this.#onStateChange({ status: 'degraded', reason, retryInMilliseconds })
    this.#retryTimer = this.#environment.setTimeout(() => {
      this.#retryTimer = null
      this.#ensureConnection()
    }, retryInMilliseconds)
  }

  #nextRetryDelay(): number {
    const exponential = Math.min(
      this.#timing.reconnectMaximumMilliseconds,
      this.#timing.reconnectBaseMilliseconds * 2 ** this.#retryCount,
    )
    const jitter = 0.5 + this.#environment.random()
    this.#retryCount += 1
    return Math.max(1, Math.round(exponential * jitter))
  }

  #handleAuthoritySensitiveClose(): void {
    this.#policyBlocked = true
    this.#cancelRetry()
    // A policy or ambiguous clean close may be logout/revocation rather than a
    // transport failure. Re-read `/auth/me` once and let
    // AuthenticationProvider remove protected UI; never spin a
    // reconnect/refresh loop from this client. Transient HTTP failure is not
    // confused with a real 401: authority is retried with the same bounded
    // backoff while protected state remains in memory.
    void this.#checkAuthority()
  }

  async #checkAuthority(): Promise<void> {
    if (!this.#running || !this.#policyBlocked || this.#authorityCheckInFlight) return
    if (!this.#environment.isOnline()) {
      this.#onStateChange({ status: 'waiting', reason: 'offline' })
      return
    }
    if (!this.#environment.isVisible()) {
      this.#onStateChange({ status: 'waiting', reason: 'hidden' })
      return
    }

    this.#authorityCheckInFlight = true
    this.#onStateChange({ status: 'checking-authority' })
    let result: 'authenticated' | 'unauthenticated' | 'unavailable'
    try {
      result = await this.#queries.refetchAuthentication()
    } catch {
      result = 'unavailable'
    } finally {
      this.#authorityCheckInFlight = false
    }
    if (!this.#running || !this.#policyBlocked) return

    if (result === 'unauthenticated') return
    if (result === 'unavailable') {
      this.#scheduleAuthorityRetry()
      return
    }

    // An authoritative HTTP read confirmed the same browser is still
    // authenticated. Treat the close as a one-off server/transport decision
    // and reconnect through the ordinary bounded resync path.
    this.#policyBlocked = false
    this.#scheduleReconnect('transport')
  }

  #scheduleAuthorityRetry(): void {
    if (!this.#running || !this.#policyBlocked || this.#retryTimer !== null) return
    if (!this.#environment.isOnline()) {
      this.#onStateChange({ status: 'waiting', reason: 'offline' })
      return
    }
    if (!this.#environment.isVisible()) {
      this.#onStateChange({ status: 'waiting', reason: 'hidden' })
      return
    }

    const retryInMilliseconds = this.#nextRetryDelay()
    this.#onStateChange({ status: 'degraded', reason: 'transport', retryInMilliseconds })
    this.#retryTimer = this.#environment.setTimeout(() => {
      this.#retryTimer = null
      void this.#checkAuthority()
    }, retryInMilliseconds)
  }

  #availabilityTimerName(
    name: 'handshake' | 'heartbeat' | 'pong',
  ): '#handshakeTimer' | '#heartbeatTimer' | '#pongTimer' {
    switch (name) {
      case 'handshake':
        return '#handshakeTimer'
      case 'heartbeat':
        return '#heartbeatTimer'
      case 'pong':
        return '#pongTimer'
    }
  }

  #clearTimer(name: 'handshake' | 'heartbeat' | 'pong'): void {
    // Private fields cannot be indexed safely; keep this small explicit map so
    // every timer is both cleared and nulled under exact-optional TS settings.
    const field = this.#availabilityTimerName(name)
    const handle =
      field === '#handshakeTimer'
        ? this.#handshakeTimer
        : field === '#heartbeatTimer'
          ? this.#heartbeatTimer
          : this.#pongTimer
    if (handle !== null) this.#environment.clearTimeout(handle)
    if (field === '#handshakeTimer') this.#handshakeTimer = null
    else if (field === '#heartbeatTimer') this.#heartbeatTimer = null
    else this.#pongTimer = null
  }

  #clearConnectionTimers(): void {
    this.#clearTimer('handshake')
    this.#clearTimer('heartbeat')
    this.#clearTimer('pong')
  }

  #cancelRetry(): void {
    if (this.#retryTimer !== null) this.#environment.clearTimeout(this.#retryTimer)
    this.#retryTimer = null
  }

  #clearAllTimers(): void {
    this.#clearConnectionTimers()
    this.#cancelRetry()
    if (this.#invalidationTimer !== null) {
      this.#environment.clearTimeout(this.#invalidationTimer)
      this.#invalidationTimer = null
    }
    this.#invalidationPending = false
    this.#invalidationResources.clear()
  }

  #detachAndCloseSocket(code: number, reason: string): void {
    const socket = this.#socket
    this.#socket = null
    if (socket === null) return
    this.#detachSocket(socket)
    try {
      socket.close(code, reason)
    } catch {
      // Cleanup must remain idempotent even for a failed browser transport.
    }
  }

  #detachSocket(socket: RealtimeSocket): void {
    socket.onopen = null
    socket.onerror = null
    socket.onmessage = null
    socket.onclose = null
  }

  #isCurrent(socket: RealtimeSocket, generation: number): boolean {
    return this.#running && this.#socket === socket && this.#socketGeneration === generation
  }
}

export interface RealtimeProviderProps {
  audience: Audience
  runtime: RuntimeConfig
  children: ReactNode
  socketFactory?: RealtimeSocketFactory
  environment?: RealtimeEnvironment
  timing?: Partial<RealtimeTiming>
}

export function RealtimeProvider({
  audience,
  runtime,
  children,
  socketFactory,
  environment,
  timing,
}: RealtimeProviderProps) {
  const authentication = useAuthentication()
  const authenticationRef = useRef(authentication)
  useEffect(() => {
    authenticationRef.current = authentication
  }, [authentication])
  const queryClient = useQueryClient()
  const [state, setState] = useState<RealtimeConnectionState>({ status: 'idle' })
  const sessionId =
    authentication.state.status === 'authenticated'
      ? authentication.state.context.currentSession.sessionId
      : null

  useEffect(() => {
    if (sessionId === null) return

    const connection = new RealtimeConnection({
      audience,
      runtime,
      queries: {
        refetchActiveQueries: async () => {
          await queryClient.refetchQueries({ type: 'active' })
        },
        invalidateActiveQueries: async (resources) => {
          await queryClient.invalidateQueries({
            predicate: (query) => shouldInvalidateRealtimeQuery(query.meta, resources),
            refetchType: 'active',
            type: 'active',
          })
        },
        refetchAuthentication: async () => {
          try {
            const context = await authenticationRef.current.client.me()
            queryClient.setQueryData(authQueryKeys.me(audience), context)
            return 'authenticated'
          } catch (error) {
            const classification = authenticationRef.current.handleApiError(error)
            return classification === 'unauthenticated' ? 'unauthenticated' : 'unavailable'
          }
        },
      },
      onStateChange: setState,
      ...(socketFactory ? { socketFactory } : {}),
      ...(environment ? { environment } : {}),
      ...(timing ? { timing } : {}),
    })
    connection.start()
    return () => connection.stop()
  }, [audience, environment, queryClient, runtime, sessionId, socketFactory, timing])

  const value = useMemo<RealtimeConnectionValue>(
    () => ({ audience, state: sessionId === null ? { status: 'idle' } : state }),
    [audience, sessionId, state],
  )
  return <RealtimeConnectionContext value={value}>{children}</RealtimeConnectionContext>
}

export function useRealtimeConnection(): RealtimeConnectionValue {
  const value = useContext(RealtimeConnectionContext)
  if (value === null) throw new Error('useRealtimeConnection must be used inside RealtimeProvider')
  return value
}
