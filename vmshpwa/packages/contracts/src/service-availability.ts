import { z } from 'zod'

export type ServiceAvailability = {
  state: 'ready' | 'updating' | 'reconnecting'
  since: number
  prolonged: boolean
  cause?: 'server' | 'unknown'
}
const ready: ServiceAvailability = { state: 'ready', since: 0, prolonged: false }

export type ServiceTransportFailure = 'offline' | 'recovering' | 'deadline' | 'network'

/** docs/performance/2026-10-08-fixes.md: intentional cache fallback is typed. */
export class ServiceTransportError extends TypeError {
  constructor(
    readonly kind: ServiceTransportFailure,
    cause?: unknown,
  ) {
    super(
      {
        offline: 'Network is offline',
        recovering: 'Network recovery in progress',
        deadline: 'Network read deadline exceeded',
        network: 'Network request failed',
      }[kind],
      { cause },
    )
    this.name = 'ServiceTransportError'
  }
}
const statusSchema = z.object({ state: z.enum(['ready', 'updating']) })
const updatingErrorSchema = z.object({ error: z.object({ code: z.literal('service_updating') }) })
const applicationErrorSchema = z.object({
  error: z.object({
    code: z.string().min(1),
    message: z.string().min(1),
    requestId: z.string().min(1),
  }),
})

/** docs/smooth-redeploy.md: one recovery loop, never replay an ambiguous write. */
export function createServiceTransport(options: {
  fetch: typeof globalThis.fetch
  origin: string
  random?: () => number
  now?: () => number
  unconfirmedMessage?: () => string
  onEpisode?: (event: { state: string; durationMs: number; prolonged: boolean }) => void
}) {
  let snapshot = ready
  const listeners = new Set<() => void>()
  const now = options.now ?? Date.now
  let recovery: Promise<void> | undefined
  const publish = (next: ServiceAvailability) => {
    snapshot = next
    listeners.forEach((listener) => listener())
  }
  const subscribe = (listener: () => void) => {
    listeners.add(listener)
    return () => {
      listeners.delete(listener)
    }
  }
  const markedUpdating = async (response: Response) => {
    if (response.status !== 503) return false
    if (response.headers.get('X-VMSH-Service-State') === 'updating') return true
    try {
      return updatingErrorSchema.safeParse(await response.clone().json()).success
    } catch {
      return false
    }
  }
  const probe = async (path: string) => {
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 5_000)
    try {
      return await options.fetch(path, {
        credentials: 'include',
        cache: 'no-store',
        signal: controller.signal,
      })
    } finally {
      clearTimeout(timeout)
    }
  }
  // docs/service-failure-copy-20261004.md: gateway errors prove a service
  // failure; a failed fetch alone does not identify the user's connection.
  const markServerFailure = () => {
    if (snapshot.state === 'reconnecting' && snapshot.cause !== 'server')
      publish({ ...snapshot, cause: 'server' })
  }
  const recover = (
    runtimePath: string,
    updating: boolean,
    cause: 'server' | 'unknown' = 'unknown',
  ): Promise<void> => {
    if (recovery) {
      if (updating && snapshot.state !== 'updating') publish({ ...snapshot, state: 'updating' })
      else if (cause === 'server') markServerFailure()
      return recovery
    }
    publish({
      state: updating ? 'updating' : 'reconnecting',
      since: now(),
      prolonged: false,
      cause,
    })
    const prolonged = setTimeout(() => {
      publish({ ...snapshot, prolonged: true })
      options.onEpisode?.({
        state: snapshot.state,
        durationMs: now() - snapshot.since,
        prolonged: true,
      })
    }, 60_000)
    recovery = (async () => {
      let attempt = 0
      try {
        for (;;) {
          const delay = [1_000, 2_000, 5_000][Math.min(attempt++, 2)]!
          await new Promise((resolve) =>
            setTimeout(resolve, delay + Math.floor((options.random ?? Math.random)() * 250)),
          )
          let gatewayReady = false
          try {
            const status = await probe('/service-status')
            if (status.ok) {
              const parsed = statusSchema.safeParse(await status.json().catch(() => null))
              if (parsed.success && parsed.data.state === 'updating') {
                if (snapshot.state !== 'updating') publish({ ...snapshot, state: 'updating' })
                continue
              }
              gatewayReady = parsed.success && parsed.data.state === 'ready'
            } else await status.body?.cancel()
            // Old installations may not have /service-status yet. A static
            // "ready" is not sufficient: confirm that Python can serve runtime.
            const response = await probe(runtimePath)
            if (await markedUpdating(response)) {
              publish({ ...snapshot, state: 'updating' })
              continue
            }
            await response.body?.cancel()
            if ([502, 503, 504].includes(response.status)) {
              markServerFailure()
              continue
            }
            // Let the real caller validate runtime / permission failures.
            break
          } catch {
            // The same-origin edge replied, but Python's runtime probe failed.
            // Do not label this as a missing internet connection.
            if (gatewayReady && !(typeof navigator !== 'undefined' && navigator.onLine === false))
              markServerFailure()
            /* One tab-wide loop also covers an unexpected outage. */
          }
        }
      } finally {
        clearTimeout(prolonged)
        const event = {
          state: snapshot.state,
          durationMs: now() - snapshot.since,
          prolonged: snapshot.prolonged,
        }
        recovery = undefined
        publish(ready)
        // A prolonged episode was already reported at the sixty-second mark.
        if (!event.prolonged) options.onEpisode?.(event)
      }
    })()
    return recovery
  }
  const wait = (pending: Promise<void>, signal?: AbortSignal | null) =>
    new Promise<void>((resolve, reject) => {
      const abort = () => {
        cleanup()
        reject(
          signal?.reason instanceof Error
            ? signal.reason
            : new DOMException('Cancelled', 'AbortError'),
        )
      }
      const cleanup = () => signal?.removeEventListener('abort', abort)
      if (signal?.aborted) {
        abort()
        return
      }
      signal?.addEventListener('abort', abort, { once: true })
      pending.then(
        () => {
          cleanup()
          resolve()
        },
        (error: unknown) => {
          cleanup()
          reject(error instanceof Error ? error : new Error('Recovery failed'))
        },
      )
    })
  const unconfirmed = () =>
    new Response(
      JSON.stringify({
        error: {
          code: 'request_not_confirmed',
          message:
            options.unconfirmedMessage?.() ??
            'The server did not confirm the action. Check the result before retrying; keep your draft.',
          requestId: 'service-recovery',
        },
      }),
      { status: 503, headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' } },
    )
  const request = async (
    input: RequestInfo | URL,
    init?: RequestInit,
    allowOfflineRead = false,
  ): Promise<Response> => {
    const url = new URL(input instanceof Request ? input.url : String(input), options.origin)
    const match = /^\/(student|family|staff)\/api\/v1\//.exec(url.pathname)
    if (url.origin !== options.origin || !match) return options.fetch(input, init)
    const runtimePath = `/${match[1]}/api/v1/runtime`
    const signal = init?.signal ?? (input instanceof Request ? input.signal : undefined)
    const method = (init?.method ?? (input instanceof Request ? input.method : 'GET')).toUpperCase()
    const read = method === 'GET' || method === 'HEAD'
    let idempotent = false
    // Explicit receipt-backed routes only, not arbitrary POSTs containing a key.
    if (
      method === 'POST' &&
      typeof init?.body === 'string' &&
      /\/(problems\/[^/]+\/test-attempts|live-marking\/operations)$/.test(url.pathname)
    ) {
      try {
        idempotent = (
          url.pathname.endsWith('/live-marking/operations')
            ? z.object({ operationId: z.string().min(1) })
            : z.object({ idempotencyKey: z.string().min(1) })
        ).safeParse(JSON.parse(init.body)).success
      } catch {
        /* Invalid bodies retain ordinary server validation. */
      }
    }
    for (;;) {
      signal?.throwIfAborted()
      // docs/smooth-redeploy.md: offline writes must return to their durable
      // outbox too, instead of waiting behind another request's recovery loop.
      if (typeof navigator !== 'undefined' && !navigator.onLine)
        throw new ServiceTransportError('offline')
      if (recovery) {
        if (read && allowOfflineRead && snapshot.state === 'reconnecting')
          throw new ServiceTransportError('recovering')
        await wait(recovery, signal)
      }
      signal?.throwIfAborted()
      let response: Response
      const startup = read && (allowOfflineRead || /\/(runtime|auth\/me)$/.test(url.pathname))
      const deadline = new AbortController()
      const timeout = startup ? setTimeout(() => deadline.abort(), 5_000) : undefined
      const abortStartup = () => deadline.abort(signal?.reason)
      if (startup) signal?.addEventListener('abort', abortStartup, { once: true })
      try {
        response = await options.fetch(
          input instanceof Request ? input.clone() : input,
          startup
            ? {
                ...init,
                signal: deadline.signal,
              }
            : init,
        )
      } catch (error) {
        if (signal?.aborted) throw error
        const pending = recover(runtimePath, false)
        if (!read && !idempotent) return unconfirmed()
        // Preserve the existing explicit offline cache boundary.
        if ((read && allowOfflineRead) || (typeof navigator !== 'undefined' && !navigator.onLine))
          throw new ServiceTransportError(deadline.signal.aborted ? 'deadline' : 'network', error)
        await wait(pending, signal)
        continue
      } finally {
        clearTimeout(timeout)
        signal?.removeEventListener('abort', abortStartup)
      }
      if (![502, 503, 504].includes(response.status)) return response
      const updating = await markedUpdating(response)
      if (!updating) {
        // docs/smooth-redeploy.md: a typed API rejection confirms the outcome;
        // keep its localized explanation and never replay the request.
        const payload: unknown = await response
          .clone()
          .json()
          .catch(() => null)
        if (applicationErrorSchema.safeParse(payload).success) return response
      }
      await response.body?.cancel()
      const pending = recover(runtimePath, updating, 'server')
      if (!read && !updating && !idempotent) return unconfirmed()
      // A marked nginx rejection was never forwarded, so even an unsafe
      // method can be sent once after recovery. Other writes never replay here.
      await wait(pending, signal)
    }
  }
  return {
    fetch: (input: RequestInfo | URL, init?: RequestInit) => request(input, init),
    fetchOfflineRead: (input: RequestInfo | URL, init?: RequestInit) => request(input, init, true),
    subscribe,
    getSnapshot: () => snapshot,
  }
}

let browserTransport: ReturnType<typeof createServiceTransport> | undefined
let unconfirmedMessage: (() => string) | undefined
export function setServiceUnconfirmedMessage(message: typeof unconfirmedMessage) {
  unconfirmedMessage = message
}
let episodeReporter:
  ((event: { state: string; durationMs: number; prolonged: boolean }) => void) | undefined
export function setServiceEpisodeReporter(reporter: typeof episodeReporter) {
  episodeReporter = reporter
}
export function getServiceTransport() {
  browserTransport ??= createServiceTransport({
    fetch: (...args) => globalThis.fetch(...args),
    origin:
      typeof location !== 'undefined' && typeof location.origin === 'string'
        ? location.origin
        : 'http://localhost',
    onEpisode: (event) => episodeReporter?.(event),
    unconfirmedMessage: () =>
      unconfirmedMessage?.() ??
      'The server did not confirm the action. Check the result before retrying; keep your draft.',
  })
  return browserTransport
}
export const pwaFetch: typeof globalThis.fetch = (...args) => getServiceTransport().fetch(...args)
/** docs/offline-current-lessons.md: cache-backed GETs escape network recovery; writes and explicit deploys retain their policy. */
export const pwaOfflineReadFetch: typeof globalThis.fetch = (...args) =>
  getServiceTransport().fetchOfflineRead(...args)
export const serviceAvailabilitySnapshot = () => browserTransport?.getSnapshot() ?? ready
export const subscribeServiceAvailability = (listener: () => void) =>
  getServiceTransport().subscribe(listener)
