import { useQuery, useQueryClient } from '@tanstack/react-query'
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

const AuthenticationContext = createContext<AuthenticationController | null>(null)

export interface AuthenticationProviderProps {
  audience: Audience
  runtime: RuntimeConfig
  children: ReactNode
  fetchImplementation?: AuthClientOptions['fetchImplementation']
  refreshCoordinator?: AuthRefreshCoordinator
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
  const queryKey = authQueryKeys.me(audience)
  const currentSessionQuery = useQuery({
    queryKey,
    queryFn: async ({ signal }) => {
      const context = await client.me({ signal })
      setClockNow(Date.now())
      return context
    },
    enabled: !locallySignedOut,
    retry: false,
    staleTime: 30_000,
    refetchOnReconnect: true,
    refetchOnWindowFocus: true,
  })

  const endLocalSession = useCallback(
    (reason?: AuthErrorCode) => {
      setLocallySignedOut(true)
      setLocalEndReason(reason)
      void queryClient.cancelQueries()
      // Account-owned server state must not survive a logout/account switch in
      // memory. Durable owner-scoped cleanup is composed by the apps later.
      queryClient.clear()
    },
    [queryClient],
  )

  const login = useCallback(
    async (request: AuthLoginRequest, options: AuthRequestOptions = {}) => {
      const context = await client.login(request, options)
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
    [client, queryClient, queryKey],
  )

  const refresh = useCallback(
    async (options: AuthRequestOptions = {}) => {
      const context = await client.refresh(options)
      queryClient.setQueryData(queryKey, context)
      setClockNow(Date.now())
      setLocallySignedOut(false)
      setLocalEndReason(undefined)
      return context
    },
    [client, queryClient, queryKey],
  )

  const logout = useCallback(
    async (options: AuthRequestOptions = {}) => {
      await client.logout(options)
      endLocalSession()
    },
    [client, endLocalSession],
  )

  const logoutAll = useCallback(
    async (options: AuthRequestOptions = {}) => {
      await client.logoutAll(options)
      endLocalSession()
    },
    [client, endLocalSession],
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
    if (!context || locallySignedOut) return
    const expiresAt = Date.parse(context.policy.sessionExpiresAt)
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
  }, [currentSessionQuery.data, endLocalSession, locallySignedOut])

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
  ])

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
