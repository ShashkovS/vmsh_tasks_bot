import { useQuery, useQueryClient } from '@tanstack/react-query'
import { setObservabilityUser } from './observability'
import {
  ApiResponseError,
  authErrorCodeSchema,
  authQueryKeys,
  type Audience,
  type AuthContext as AuthSessionContext,
  type AuthErrorCode,
  type Principal,
  type RuntimeConfig,
} from '@vmsh/contracts'
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'

import {
  AuthNetworkError,
  classifyAuthApiError,
  classifyAuthLoginError,
  createAuthClient,
  type AuthApiAccessFailure,
  type AuthClient,
  type AuthClientOptions,
  type AuthLoginRequest,
  type AuthLoginFailure,
  type AuthRequestOptions,
} from './auth-client'
import type { AuthRefreshCoordinator } from './auth-refresh-coordinator'

export type AuthenticationState =
  | { status: 'checking' }
  | { status: 'authenticated'; context: AuthSessionContext; principal: Principal }
  | { status: 'unauthenticated'; reason?: AuthErrorCode }
  | {
      status: 'offline-unverified'
      error: AuthNetworkError
      context?: AuthSessionContext
      principal?: Principal
      sessionExpiresAt?: string
    }
  | { status: 'error'; error: unknown }

export interface AuthenticationController {
  readonly audience: Audience
  readonly client: AuthClient
  readonly state: AuthenticationState
  login(request: AuthLoginRequest, options?: AuthRequestOptions): Promise<AuthSessionContext>
  refresh(options?: AuthRequestOptions): Promise<AuthSessionContext>
  logout(options?: AuthRequestOptions): Promise<void>
  logoutAll(options?: AuthRequestOptions): Promise<void>
  retry(): Promise<void>
  handleApiError(error: unknown): AuthApiAccessFailure
}

export type AuthLoginAttemptState = 'idle' | 'pending' | AuthLoginFailure

export interface AuthenticationLoginController {
  readonly isResolvingSession: boolean
  readonly loginState: AuthLoginAttemptState
  submit(request: AuthLoginRequest): Promise<boolean>
}

/**
 * Secret-free durable identity used only to unlock owner-scoped cached data.
 * The store must never persist cookies, credentials, access tokens or the
 * server session ID. See Phase 3 in `07-phase-3-student-reading.md`.
 */
export interface PersistedAuthenticationSnapshot {
  audience: Extract<Audience, 'student' | 'family'>
  ownerId: string
  principal: Principal
  sessionExpiresAt: string
  cachedAt: string
}

export interface AuthenticationOfflineStore {
  read(): Promise<PersistedAuthenticationSnapshot | null>
  save(context: AuthSessionContext): Promise<PersistedAuthenticationSnapshot>
  clear(): Promise<void>
}

const AuthenticationContext = createContext<AuthenticationController | null>(null)

export interface AuthenticationProviderProps {
  audience: Audience
  runtime: RuntimeConfig
  children: ReactNode
  fetchImplementation?: AuthClientOptions['fetchImplementation']
  refreshCoordinator?: AuthRefreshCoordinator
  offlineStore?: AuthenticationOfflineStore
}

/**
 * Memory-only authentication authority for one browser audience.
 *
 * Cookies remain HttpOnly and the server remains authoritative. No principal,
 * access token or refresh secret is persisted in Web Storage. See Phase 1 in
 * `dev/development-plan/05-phase-1-auth.md`.
 */
export function AuthenticationProvider({
  audience,
  runtime,
  children,
  fetchImplementation,
  refreshCoordinator,
  offlineStore,
}: AuthenticationProviderProps) {
  const queryClient = useQueryClient()
  const client = useMemo(
    () =>
      createAuthClient(audience, runtime, {
        ...(fetchImplementation ? { fetchImplementation } : {}),
        ...(refreshCoordinator ? { refreshCoordinator } : {}),
      }),
    [audience, fetchImplementation, refreshCoordinator, runtime],
  )
  const [locallySignedOut, setLocallySignedOut] = useState(false)
  const [localEndReason, setLocalEndReason] = useState<AuthErrorCode | undefined>()
  const [clockNow, setClockNow] = useState(() => Date.now())
  const [offlineSnapshotState, setOfflineSnapshotState] = useState<
    { status: 'loading' } | { status: 'ready'; snapshot: PersistedAuthenticationSnapshot | null }
  >(() =>
    offlineStore === undefined ? { status: 'ready', snapshot: null } : { status: 'loading' },
  )
  const queryKey = authQueryKeys.me(audience)

  useEffect(() => {
    let active = true
    if (!offlineStore) {
      return () => {
        active = false
      }
    }
    void offlineStore.read().then(
      (snapshot) => {
        if (active) setOfflineSnapshotState({ status: 'ready', snapshot })
      },
      () => {
        // An unreadable local snapshot never widens access. Online auth may
        // still succeed; cold offline remains fail-closed.
        if (active) setOfflineSnapshotState({ status: 'ready', snapshot: null })
      },
    )
    return () => {
      active = false
    }
  }, [offlineStore])

  const persistContext = useCallback(
    async (context: AuthSessionContext) => {
      if (!offlineStore) return
      const snapshot = await offlineStore.save(context)
      setOfflineSnapshotState({ status: 'ready', snapshot })
    },
    [offlineStore],
  )

  const clearOfflineSnapshot = useCallback(async () => {
    setOfflineSnapshotState({ status: 'ready', snapshot: null })
    await offlineStore?.clear()
  }, [offlineStore])

  const currentSessionQuery = useQuery({
    queryKey,
    queryFn: async ({ signal }) => {
      try {
        const context = await client.me({ signal })
        await persistContext(context)
        setClockNow(Date.now())
        return context
      } catch (error) {
        if (classifyAuthApiError(error) === 'unauthenticated') {
          await clearOfflineSnapshot()
        }
        throw error
      }
    },
    enabled: !locallySignedOut,
    retry: false,
    staleTime: 30_000,
    refetchOnReconnect: true,
    refetchOnWindowFocus: true,
  })

  const endLocalSession = useCallback(
    (reason?: AuthErrorCode, clearOffline = true) => {
      setLocallySignedOut(true)
      setLocalEndReason(reason)
      void queryClient.cancelQueries()
      // Account-owned server state must not survive a logout/account switch in
      // memory; the optional durable store removes the same owner's local data.
      queryClient.clear()
      if (clearOffline) void clearOfflineSnapshot().catch(() => undefined)
    },
    [clearOfflineSnapshot, queryClient],
  )

  const login = useCallback(
    async (request: AuthLoginRequest, options: AuthRequestOptions = {}) => {
      const context = await client.login(request, options)
      await persistContext(context)
      await queryClient.cancelQueries()
      // Keep the active `/me` observer mounted while dropping every query that
      // may belong to the previous account. Removing that observer with
      // `clear()` can leave its earlier 401 visible after a successful retry.
      queryClient.removeQueries({
        predicate: (query) =>
          !(
            query.queryKey.length === queryKey.length &&
            query.queryKey.every((part, index) => part === queryKey[index])
          ),
      })
      queryClient.setQueryData(queryKey, context)
      setClockNow(Date.now())
      setLocallySignedOut(false)
      setLocalEndReason(undefined)
      return context
    },
    [client, persistContext, queryClient, queryKey],
  )

  const refresh = useCallback(
    async (options: AuthRequestOptions = {}) => {
      const context = await client.refresh(options)
      await persistContext(context)
      queryClient.setQueryData(queryKey, context)
      setClockNow(Date.now())
      setLocallySignedOut(false)
      setLocalEndReason(undefined)
      return context
    },
    [client, persistContext, queryClient, queryKey],
  )

  const logout = useCallback(
    async (options: AuthRequestOptions = {}) => {
      await client.logout(options)
      await clearOfflineSnapshot()
      endLocalSession(undefined, false)
    },
    [clearOfflineSnapshot, client, endLocalSession],
  )

  const logoutAll = useCallback(
    async (options: AuthRequestOptions = {}) => {
      await client.logoutAll(options)
      await clearOfflineSnapshot()
      endLocalSession(undefined, false)
    },
    [clearOfflineSnapshot, client, endLocalSession],
  )

  const retry = useCallback(async () => {
    setLocallySignedOut(false)
    setLocalEndReason(undefined)
    const result = await currentSessionQuery.refetch()
    if (result.error) throw result.error
  }, [currentSessionQuery])

  const handleApiError = useCallback(
    (error: unknown) => {
      const classification = classifyAuthApiError(error)
      if (classification === 'unauthenticated') {
        const reason =
          error instanceof ApiResponseError ? authErrorCodeSchema.safeParse(error.code) : undefined
        endLocalSession(reason?.success ? reason.data : undefined)
      }
      return classification
    },
    [endLocalSession],
  )

  useEffect(() => {
    const context = currentSessionQuery.data
    const cachedExpiry =
      offlineSnapshotState.status === 'ready'
        ? offlineSnapshotState.snapshot?.sessionExpiresAt
        : undefined
    const sessionExpiresAt = context?.policy.sessionExpiresAt ?? cachedExpiry
    if (!sessionExpiresAt || locallySignedOut) return
    const expiresAt = Date.parse(sessionExpiresAt)
    let timeout: ReturnType<typeof setTimeout> | undefined

    const scheduleExpiryCheck = () => {
      if (timeout) clearTimeout(timeout)
      const remaining = Number.isFinite(expiresAt) ? expiresAt - Date.now() : 0
      if (remaining <= 0) {
        endLocalSession('session_expired')
        return
      }
      timeout = setTimeout(
        () => {
          scheduleExpiryCheck()
        },
        Math.min(remaining + 1, 2_147_483_647),
      )
    }
    const checkAfterBrowserResume = () => scheduleExpiryCheck()

    scheduleExpiryCheck()
    if (typeof window !== 'undefined') {
      window.addEventListener('focus', checkAfterBrowserResume)
      window.addEventListener('pageshow', checkAfterBrowserResume)
      document.addEventListener('visibilitychange', checkAfterBrowserResume)
    }
    return () => {
      if (timeout) clearTimeout(timeout)
      if (typeof window !== 'undefined') {
        window.removeEventListener('focus', checkAfterBrowserResume)
        window.removeEventListener('pageshow', checkAfterBrowserResume)
        document.removeEventListener('visibilitychange', checkAfterBrowserResume)
      }
    }
  }, [currentSessionQuery.data, endLocalSession, locallySignedOut, offlineSnapshotState])

  const state = useMemo<AuthenticationState>(() => {
    if (locallySignedOut) {
      return localEndReason
        ? { status: 'unauthenticated', reason: localEndReason }
        : { status: 'unauthenticated' }
    }

    const verifiedContext = currentSessionQuery.data
    if (verifiedContext) {
      const expiresAt = Date.parse(verifiedContext.policy.sessionExpiresAt)
      if (!Number.isFinite(expiresAt) || clockNow >= expiresAt) {
        return { status: 'unauthenticated', reason: 'session_expired' }
      }
    }

    const queryError = currentSessionQuery.error
    if (queryError) {
      if (classifyAuthApiError(queryError) === 'unauthenticated') {
        const parsedReason =
          queryError instanceof ApiResponseError
            ? authErrorCodeSchema.safeParse(queryError.code)
            : undefined
        return parsedReason?.success
          ? { status: 'unauthenticated', reason: parsedReason.data }
          : { status: 'unauthenticated' }
      }
      if (queryError instanceof AuthNetworkError) {
        // A principal already verified in this tab remains usable through a
        // transient refetch failure. Cold start has no in-memory principal and
        // therefore fails closed as offline-unverified.
        if (verifiedContext) {
          return {
            status: 'offline-unverified',
            error: queryError,
            context: verifiedContext,
            principal: verifiedContext.principal,
            sessionExpiresAt: verifiedContext.policy.sessionExpiresAt,
          }
        }
        if (offlineSnapshotState.status === 'loading') return { status: 'checking' }
        const snapshot = offlineSnapshotState.snapshot
        if (snapshot && clockNow < Date.parse(snapshot.sessionExpiresAt)) {
          return {
            status: 'offline-unverified',
            error: queryError,
            principal: snapshot.principal,
            sessionExpiresAt: snapshot.sessionExpiresAt,
          }
        }
        return { status: 'offline-unverified', error: queryError }
      }
      return { status: 'error', error: queryError }
    }

    if (verifiedContext) {
      return {
        status: 'authenticated',
        context: verifiedContext,
        principal: verifiedContext.principal,
      }
    }
    return { status: 'checking' }
  }, [
    clockNow,
    currentSessionQuery.data,
    currentSessionQuery.error,
    localEndReason,
    locallySignedOut,
    offlineSnapshotState,
  ])

  const observabilityAccountId = authenticationStatePrincipal(state)?.accountId ?? null
  useEffect(() => {
    setObservabilityUser(observabilityAccountId)
    return () => setObservabilityUser(null)
  }, [observabilityAccountId])

  const value = useMemo<AuthenticationController>(
    () => ({
      audience,
      client,
      state,
      login,
      refresh,
      logout,
      logoutAll,
      retry,
      handleApiError,
    }),
    [audience, client, handleApiError, login, logout, logoutAll, refresh, retry, state],
  )

  return <AuthenticationContext value={value}>{children}</AuthenticationContext>
}

export function useAuthentication(): AuthenticationController {
  const authentication = useContext(AuthenticationContext)
  if (!authentication) {
    throw new Error('useAuthentication must be used inside AuthenticationProvider')
  }
  return authentication
}

export function authenticationStatePrincipal(state: AuthenticationState): Principal | null {
  if (state.status === 'authenticated') return state.principal
  if (state.status === 'offline-unverified') return state.principal ?? null
  return null
}

export function useAuthenticatedPrincipal(): Principal {
  const { state } = useAuthentication()
  const principal = authenticationStatePrincipal(state)
  if (!principal) {
    throw new Error('useAuthenticatedPrincipal requires an authenticated boundary')
  }
  return principal
}

/**
 * Public-login orchestration shared by all three route adapters. The app owns
 * its exact credential schema and safe redirect, while this hook prevents a
 * protected principal from lingering on `/login`.
 */
export function useAuthenticationLogin(
  onAuthenticated: (context: AuthSessionContext) => void,
): AuthenticationLoginController {
  const authentication = useAuthentication()
  const [attemptState, setAttemptState] = useState<AuthLoginAttemptState>('idle')
  const redirectedSessionId = useRef<string | null>(null)

  useEffect(() => {
    if (authentication.state.status !== 'authenticated') {
      redirectedSessionId.current = null
      return
    }
    const sessionId = authentication.state.context.currentSession.sessionId
    if (redirectedSessionId.current === sessionId) return
    redirectedSessionId.current = sessionId
    onAuthenticated(authentication.state.context)
  }, [authentication.state, onAuthenticated])

  const submit = useCallback(
    async (request: AuthLoginRequest): Promise<boolean> => {
      setAttemptState('pending')
      try {
        await authentication.login(request)
        setAttemptState('idle')
        return true
      } catch (error) {
        setAttemptState(classifyAuthLoginError(error))
        return false
      }
    },
    [authentication],
  )

  const loginState = useMemo<AuthLoginAttemptState>(() => {
    if (attemptState !== 'idle') return attemptState
    if (authentication.state.status === 'offline-unverified') return 'network'
    if (authentication.state.status === 'error') return 'error'
    return 'idle'
  }, [attemptState, authentication.state.status])

  return {
    isResolvingSession:
      authentication.state.status === 'checking' || authentication.state.status === 'authenticated',
    loginState,
    submit,
  }
}
