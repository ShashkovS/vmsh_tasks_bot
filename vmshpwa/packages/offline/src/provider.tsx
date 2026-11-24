import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'

import { VmshOfflineDatabase, type OfflineRuntime } from './database'

const OfflineDatabaseContext = createContext<VmshOfflineDatabase | null>(null)
export const DEFAULT_OFFLINE_DATABASE_OPEN_TIMEOUT_MS = 10_000

export class OfflineDatabaseOpenTimeoutError extends Error {
  constructor(databaseName: string) {
    super(`Opening offline database ${databaseName} timed out`)
    this.name = 'OfflineDatabaseOpenTimeoutError'
  }
}

export class OfflineDatabaseBlockedError extends Error {
  constructor(databaseName: string) {
    super(`Opening offline database ${databaseName} was blocked by another tab`)
    this.name = 'OfflineDatabaseBlockedError'
  }
}

export class OfflineDatabaseClosedError extends Error {
  constructor(databaseName: string) {
    super(`Offline database ${databaseName} closed unexpectedly`)
    this.name = 'OfflineDatabaseClosedError'
  }
}

export interface OfflineDatabaseProviderProps {
  runtime: OfflineRuntime
  children: ReactNode
  loadingFallback: ReactNode
  errorFallback: (options: { error: unknown; retry: () => void }) => ReactNode
  openTimeoutMilliseconds?: number
}

/**
 * Bound the IndexedDB upgrade handshake and turn a blocking old tab into an
 * actionable state. Workbox/Dexie readiness must never leave the application
 * spinner hanging indefinitely; see Phase 0's offline lifecycle proof.
 */
export function openOfflineDatabaseWithDeadline(
  database: VmshOfflineDatabase,
  timeoutMilliseconds = DEFAULT_OFFLINE_DATABASE_OPEN_TIMEOUT_MS,
): Promise<void> {
  if (!Number.isFinite(timeoutMilliseconds) || timeoutMilliseconds <= 0) {
    return Promise.reject(new RangeError('Offline database timeout must be positive'))
  }

  return new Promise((resolve, reject) => {
    let settled = false
    const settle = (outcome: () => void) => {
      if (settled) return
      settled = true
      window.clearTimeout(timeout)
      database.on.blocked.unsubscribe(onBlocked)
      outcome()
    }
    const onBlocked = () => settle(() => reject(new OfflineDatabaseBlockedError(database.name)))
    const timeout = window.setTimeout(
      () => settle(() => reject(new OfflineDatabaseOpenTimeoutError(database.name))),
      timeoutMilliseconds,
    )

    database.on('blocked', onBlocked)
    void database.open().then(
      () => settle(resolve),
      (error: unknown) => {
        const rejection =
          error instanceof Error ? error : new Error('IndexedDB open rejected without an Error')
        settle(() => reject(rejection))
      },
    )
  })
}

/**
 * Opens the audience database before consumers mount and closes it on every
 * teardown. See Phase 0 in `dev/development-plan/04-phase-0-baseline.md`.
 */
export function OfflineDatabaseProvider({
  runtime,
  children,
  loadingFallback,
  errorFallback,
  openTimeoutMilliseconds = DEFAULT_OFFLINE_DATABASE_OPEN_TIMEOUT_MS,
}: OfflineDatabaseProviderProps) {
  const { audience, instance } = runtime
  const database = useMemo(
    () => new VmshOfflineDatabase({ audience, instance }),
    [audience, instance],
  )

  return (
    <OfflineDatabaseLifecycle
      database={database}
      errorFallback={errorFallback}
      key={database.name}
      loadingFallback={loadingFallback}
      openTimeoutMilliseconds={openTimeoutMilliseconds}
    >
      {children}
    </OfflineDatabaseLifecycle>
  )
}

function OfflineDatabaseLifecycle({
  database,
  children,
  loadingFallback,
  errorFallback,
  openTimeoutMilliseconds,
}: Omit<OfflineDatabaseProviderProps, 'runtime'> & { database: VmshOfflineDatabase }) {
  const [attempt, setAttempt] = useState(0)
  const [state, setState] = useState<
    { status: 'opening' } | { status: 'ready' } | { status: 'error'; error: unknown }
  >({ status: 'opening' })
  const lifecycleGeneration = useRef(0)

  useEffect(() => {
    const generation = ++lifecycleGeneration.current
    let active = true
    let expectedClose = false
    const onClose = () => {
      if (active && !expectedClose) {
        setState({ status: 'error', error: new OfflineDatabaseClosedError(database.name) })
      }
    }
    database.on('close', onClose)

    void openOfflineDatabaseWithDeadline(database, openTimeoutMilliseconds).then(
      () => {
        if (active) setState({ status: 'ready' })
      },
      (error: unknown) => {
        if (active) {
          // Cancel a still-pending IndexedDB open, but keep explicit retry
          // possible on this same instance.
          expectedClose = true
          database.close({ disableAutoOpen: false })
          setState({ status: 'error', error })
        }
      },
    )

    return () => {
      active = false
      database.on.close.unsubscribe(onClose)
      // React StrictMode performs setup→cleanup→setup once in development.
      // Deferring the close by one microtask lets the second setup supersede
      // the probe cleanup, while a real unmount still closes the exact DB.
      // See `database.test.tsx` and Phase 0 runtime isolation.
      queueMicrotask(() => {
        // eslint-disable-next-line react-hooks/exhaustive-deps -- the changed ref is the cancellation signal
        if (lifecycleGeneration.current === generation) database.close()
      })
    }
  }, [attempt, database, openTimeoutMilliseconds])

  if (state.status === 'opening') return loadingFallback
  if (state.status === 'error') {
    return errorFallback({
      error: state.error,
      retry: () => {
        setState({ status: 'opening' })
        setAttempt((currentAttempt) => currentAttempt + 1)
      },
    })
  }

  return <OfflineDatabaseContext value={database}>{children}</OfflineDatabaseContext>
}

export function useOfflineDatabase(): VmshOfflineDatabase {
  const database = useContext(OfflineDatabaseContext)
  if (!database) {
    throw new Error('useOfflineDatabase must be used inside an opened OfflineDatabaseProvider')
  }
  return database
}
