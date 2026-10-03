import type { Audience } from '@vmsh/contracts'

/**
 * Same-origin refresh coordination for the single-use refresh-cookie protocol.
 *
 * Web Locks is the correctness path on supported production browsers. The
 * fallback deliberately never elects a leader with localStorage (which cannot
 * provide an atomic lease): it waits for a completion signal and executes only
 * the caller's `/auth/me` recheck. See Phase 1 in
 * `dev/development-plan/05-phase-1-auth.md`.
 */

export interface AuthRefreshCoordinator {
  coordinate<T>(leader: () => Promise<T>, follower: () => Promise<T>): Promise<T>
}

export interface AuthWebLockManager {
  request<T>(name: string, options: { mode: 'exclusive' }, callback: () => Promise<T>): Promise<T>
}

export interface BrowserRefreshCoordinatorOptions {
  lockManager?: AuthWebLockManager | null
  waitForFallbackSignal?: (audience: Audience) => Promise<void>
  notifyFallbackWaiters?: (audience: Audience) => void
}

const FALLBACK_WAIT_FOREGROUND_MS = 250
const FALLBACK_WAIT_BACKGROUND_MS = 1_500

function browserLockManager(): AuthWebLockManager | null {
  if (typeof navigator === 'undefined' || !navigator.locks) return null
  return navigator.locks
}

function refreshChannelName(audience: Audience): string {
  return `vmshpwa-auth-refresh-v1:${audience}`
}

function refreshStorageKey(audience: Audience): string {
  return `vmshpwa:auth-refresh-complete:v1:${audience}`
}

function fallbackWaitDuration(): number {
  if (typeof document === 'undefined') return 0
  return document.visibilityState === 'visible' && document.hasFocus()
    ? FALLBACK_WAIT_FOREGROUND_MS
    : FALLBACK_WAIT_BACKGROUND_MS
}

function waitForBrowserRefreshSignal(audience: Audience): Promise<void> {
  if (typeof window === 'undefined') return Promise.resolve()

  return new Promise((resolve) => {
    let completed = false
    let channel: BroadcastChannel | null = null
    const finish = () => {
      if (completed) return
      completed = true
      window.clearTimeout(timeout)
      window.removeEventListener('storage', onStorage)
      channel?.close()
      resolve()
    }
    const onStorage = (event: StorageEvent) => {
      if (event.key === refreshStorageKey(audience)) finish()
    }
    const timeout = window.setTimeout(finish, fallbackWaitDuration())

    window.addEventListener('storage', onStorage)
    if (typeof BroadcastChannel !== 'undefined') {
      channel = new BroadcastChannel(refreshChannelName(audience))
      channel.addEventListener('message', finish, { once: true })
    }
  })
}

function notifyBrowserRefreshWaiters(audience: Audience): void {
  if (typeof window === 'undefined') return
  if (typeof BroadcastChannel !== 'undefined') {
    const channel = new BroadcastChannel(refreshChannelName(audience))
    channel.postMessage({ type: 'refresh-attempt-finished', version: 1 })
    channel.close()
  }
  try {
    // This marker contains no account/session/token data. It is only a wake-up
    // edge for a no-Web-Locks follower, never a lock or source of authority.
    window.localStorage.setItem(refreshStorageKey(audience), String(Date.now()))
  } catch {
    // Storage-denied contexts still use BroadcastChannel or the bounded wait.
  }
}

export function createBrowserAuthRefreshCoordinator(
  audience: Audience,
  options: BrowserRefreshCoordinatorOptions = {},
): AuthRefreshCoordinator {
  const lockManager = options.lockManager === undefined ? browserLockManager() : options.lockManager
  const waitForFallbackSignal = options.waitForFallbackSignal ?? waitForBrowserRefreshSignal
  const notifyFallbackWaiters = options.notifyFallbackWaiters ?? notifyBrowserRefreshWaiters
  const lockName = `vmshpwa-auth-refresh-v1:${audience}`

  return {
    async coordinate<T>(leader: () => Promise<T>, follower: () => Promise<T>): Promise<T> {
      if (!lockManager) {
        await waitForFallbackSignal(audience)
        // Fail closed: localStorage/BroadcastChannel only wakes this recheck;
        // it never grants permission to consume a refresh secret.
        return follower()
      }

      return lockManager.request(lockName, { mode: 'exclusive' }, async () => {
        try {
          return await leader()
        } finally {
          notifyFallbackWaiters(audience)
        }
      })
    },
  }
}

/** Deterministic same-realm coordinator for unit tests and non-browser hosts. */
export function createInMemoryAuthRefreshCoordinator(): AuthRefreshCoordinator {
  let tail = Promise.resolve()
  return {
    coordinate<T>(leader: () => Promise<T>): Promise<T> {
      const result = tail.then(leader, leader)
      tail = result.then(
        () => undefined,
        () => undefined,
      )
      return result
    },
  }
}
