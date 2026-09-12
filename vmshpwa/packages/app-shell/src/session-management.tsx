import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  authQueryKeys,
  type AuthSessionSummary,
  type AuthSessionsResponse,
  type SessionPublicId,
} from '@vmsh/contracts'
import {
  AlertTriangle,
  Laptop,
  LoaderCircle,
  LogOut,
  MonitorSmartphone,
  RefreshCw,
  ShieldCheck,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'

import {
  Alert,
  AlertContent,
  AlertDescription,
  AlertTitle,
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Skeleton,
} from '@vmsh/ui'

import { AuthNetworkError, AuthProtocolError } from './auth-client'
import { authenticationStatePrincipal, useAuthentication } from './auth-context'

/**
 * Domain-neutral device/session surface for Phase 1.
 *
 * The server remains authoritative and opaque session IDs are used only as
 * mutation keys, never as the primary user-facing device label. See
 * `dev/development-plan/05-phase-1-auth.md` and the Storybook evidence in
 * `session-management.stories.tsx`.
 */

export type SessionManagementLoadState =
  | { status: 'loading' }
  | { status: 'error'; kind: 'network' | 'invalid' | 'other' }
  | { status: 'ready'; sessions: readonly AuthSessionSummary[] }

export type SessionEndIntent =
  | { kind: 'current'; sessionId: SessionPublicId }
  | { kind: 'other'; sessionId: SessionPublicId }
  | { kind: 'all' }

export type OfflineWorkInspection =
  { status: 'empty' } | { status: 'pending'; queuedCount?: number }

/**
 * Adapter point for the later owner-scoped Dexie/outbox implementation.
 * Phase 1 can already warn and fail closed without pretending that a durable
 * outbox exists. Cleanup is called only after the server confirms logout.
 */
export interface SessionOfflineWorkGuard {
  inspect: (
    intent: Extract<SessionEndIntent, { kind: 'current' | 'all' }>,
  ) => OfflineWorkInspection | Promise<OfflineWorkInspection>
  afterConfirmedSessionEnd?: (
    intent: Extract<SessionEndIntent, { kind: 'current' | 'all' }>,
    inspection: OfflineWorkInspection,
  ) => void | Promise<void>
}

export interface SessionManagementViewProps {
  state: SessionManagementLoadState
  onEndSession: (intent: SessionEndIntent) => Promise<void>
  onRetry?: () => void | Promise<void>
  offlineWorkGuard?: SessionOfflineWorkGuard
  title?: string
}

interface PreparedSessionEnd {
  intent: SessionEndIntent
  deviceName: string
  offlineWork: OfflineWorkInspection
}

function sessionDeviceName(session: AuthSessionSummary): string {
  return session.deviceLabel ?? session.userAgentFamily ?? 'Неизвестное устройство'
}

function sessionBrowserLabel(session: AuthSessionSummary): string | null {
  if (!session.userAgentFamily || session.userAgentFamily === session.deviceLabel) return null
  return session.userAgentFamily
}

function formatSessionTime(value: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    month: 'long',
    timeZone: 'Europe/Moscow',
  }).format(new Date(value))
}

function sessionListIntegrityIssue(sessions: readonly AuthSessionSummary[]): string | null {
  if (sessions.length === 0) return 'Сервер не подтвердил текущую сессию.'
  if (sessions.filter((session) => session.isCurrent).length !== 1) {
    return 'Сервер вернул противоречивый список сессий.'
  }
  const audiences = new Set(sessions.map((session) => session.audience))
  if (audiences.size !== 1) return 'Сервер смешал сессии разных кабинетов.'
  const identifiers = new Set(sessions.map((session) => session.sessionId))
  if (identifiers.size !== sessions.length) return 'Сервер вернул повторяющиеся сессии.'
  return null
}

function actionKey(intent: SessionEndIntent): string {
  return intent.kind === 'all' ? 'all' : `${intent.kind}:${intent.sessionId}`
}

function isLocalEndIntent(
  intent: SessionEndIntent,
): intent is Extract<SessionEndIntent, { kind: 'current' | 'all' }> {
  return intent.kind === 'current' || intent.kind === 'all'
}

function confirmationTitle(intent: SessionEndIntent): string {
  if (intent.kind === 'all') return 'Выйти на всех устройствах?'
  if (intent.kind === 'current') return 'Выйти на этом устройстве?'
  return 'Завершить сессию?'
}

function confirmationDescription(prepared: PreparedSessionEnd): string {
  if (prepared.intent.kind === 'all') {
    return 'Вход будет завершён на всех ваших устройствах. Чтобы продолжить работу, потребуется войти снова.'
  }
  if (prepared.intent.kind === 'current') {
    return 'На этом устройстве потребуется войти снова.'
  }
  return `На устройстве «${prepared.deviceName}» потребуется войти снова.`
}

function offlineWorkWarning(inspection: OfflineWorkInspection): string | null {
  if (inspection.status !== 'pending') return null
  if (inspection.queuedCount === undefined) {
    return 'Есть неотправленная работа. После выхода локальная очередь может быть удалена.'
  }
  const count = Math.max(0, Math.trunc(inspection.queuedCount))
  const mod100 = count % 100
  const mod10 = count % 10
  const suffix =
    mod10 === 1 && mod100 !== 11
      ? 'неотправленное действие'
      : mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)
        ? 'неотправленных действия'
        : 'неотправленных действий'
  return `В локальной очереди ${count} ${suffix}. После выхода они могут быть удалены.`
}

function SessionRow({
  actionPending,
  onRequestEnd,
  session,
}: {
  actionPending: boolean
  onRequestEnd: (intent: SessionEndIntent, deviceName: string) => void
  session: AuthSessionSummary
}) {
  const deviceName = sessionDeviceName(session)
  const mobile = /android|iphone|ipad|mobile/i.test(
    `${session.deviceLabel ?? ''} ${session.userAgentFamily ?? ''}`,
  )
  const DeviceIcon = mobile ? MonitorSmartphone : Laptop
  const intent: SessionEndIntent = session.isCurrent
    ? { kind: 'current', sessionId: session.sessionId }
    : { kind: 'other', sessionId: session.sessionId }

  return (
    <li className="flex min-w-0 items-start gap-3 py-3">
      <span className="mt-0.5 rounded-md bg-surface-subtle p-2 text-muted-foreground">
        <DeviceIcon aria-hidden="true" className="size-4" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium text-foreground">{deviceName}</span>
          {session.isCurrent ? <Badge variant="info">Это устройство</Badge> : null}
        </div>
        {sessionBrowserLabel(session) ? (
          <p className="mt-0.5 text-caption text-muted-foreground">
            {sessionBrowserLabel(session)}
          </p>
        ) : null}
        <p className="mt-1 text-caption text-muted-foreground">
          Последняя активность: {formatSessionTime(session.lastSeenAt)}
        </p>
      </div>
      <Button
        aria-label={
          session.isCurrent
            ? 'Выйти на этом устройстве'
            : `Завершить сессию на устройстве ${deviceName}`
        }
        disabled={actionPending}
        onClick={() => onRequestEnd(intent, deviceName)}
        size="sm"
        variant={session.isCurrent ? 'outline' : 'ghost'}
      >
        {actionPending ? <LoaderCircle aria-hidden="true" className="animate-spin" /> : null}
        {session.isCurrent ? 'Выйти' : 'Завершить'}
      </Button>
    </li>
  )
}

export function SessionManagementView({
  state,
  onEndSession,
  onRetry,
  offlineWorkGuard,
  title = 'Устройства и сессии',
}: SessionManagementViewProps) {
  const [preparedEnd, setPreparedEnd] = useState<PreparedSessionEnd | null>(null)
  const [preparingKey, setPreparingKey] = useState<string | null>(null)
  const [endingKey, setEndingKey] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const integrityIssue = state.status === 'ready' ? sessionListIntegrityIssue(state.sessions) : null
  const canManage = state.status === 'ready' && integrityIssue === null

  const requestEnd = useCallback(
    async (intent: SessionEndIntent, deviceName: string) => {
      setActionError(null)
      const key = actionKey(intent)
      setPreparingKey(key)
      try {
        const offlineWork =
          isLocalEndIntent(intent) && offlineWorkGuard
            ? await offlineWorkGuard.inspect(intent)
            : ({ status: 'empty' } satisfies OfflineWorkInspection)
        setPreparedEnd({ intent, deviceName, offlineWork })
      } catch {
        setActionError(
          'Не удалось проверить локальную очередь. Выход не выполнен; повторите попытку.',
        )
      } finally {
        setPreparingKey(null)
      }
    },
    [offlineWorkGuard],
  )

  const confirmEnd = useCallback(async () => {
    if (!preparedEnd) return
    const key = actionKey(preparedEnd.intent)
    setActionError(null)
    setEndingKey(key)
    try {
      await onEndSession(preparedEnd.intent)
    } catch {
      setPreparedEnd(null)
      setActionError('Не удалось завершить сессию. Ничего не изменено; повторите попытку.')
      setEndingKey(null)
      return
    }

    // Cleanup must never run before the authoritative server logout. The
    // promise continues even if the authenticated route unmounts immediately.
    try {
      if (isLocalEndIntent(preparedEnd.intent)) {
        await offlineWorkGuard?.afterConfirmedSessionEnd?.(
          preparedEnd.intent,
          preparedEnd.offlineWork,
        )
      }
    } catch {
      setActionError(
        'Сессия завершена, но локальные данные не удалось очистить. Закройте приложение на общем устройстве.',
      )
    }
    setPreparedEnd(null)
    setEndingKey(null)
  }, [offlineWorkGuard, onEndSession, preparedEnd])

  const pendingKey = endingKey ?? preparingKey

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ShieldCheck aria-hidden="true" className="size-4 text-muted-foreground" />
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {state.status === 'loading' ? (
          <div aria-label="Загрузка списка устройств" className="space-y-3" role="status">
            {[0, 1].map((item) => (
              <div className="flex items-center gap-3" key={item}>
                <Skeleton className="size-9 shrink-0" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-4 w-2/5" />
                  <Skeleton className="h-3 w-3/5" />
                </div>
              </div>
            ))}
          </div>
        ) : null}

        {state.status === 'error' ? (
          <Alert role="alert" tone={state.kind === 'network' ? 'warning' : 'danger'}>
            <AlertTriangle aria-hidden="true" />
            <AlertContent>
              <AlertTitle>
                {state.kind === 'network'
                  ? 'Не удалось загрузить устройства'
                  : 'Не удалось безопасно открыть список сессий'}
              </AlertTitle>
              <AlertDescription>
                {state.kind === 'network'
                  ? 'Проверьте соединение и повторите попытку.'
                  : 'Действия с сессиями отключены. Обновите данные перед повторной попыткой.'}
              </AlertDescription>
              {onRetry ? (
                <Button className="mt-2" onClick={() => void onRetry()} size="sm" variant="outline">
                  <RefreshCw aria-hidden="true" /> Повторить
                </Button>
              ) : null}
            </AlertContent>
          </Alert>
        ) : null}

        {state.status === 'ready' && integrityIssue ? (
          <Alert role="alert" tone="danger">
            <AlertTriangle aria-hidden="true" />
            <AlertContent>
              <AlertTitle>Список сессий не подтверждён</AlertTitle>
              <AlertDescription>{integrityIssue} Действия временно отключены.</AlertDescription>
              {onRetry ? (
                <Button className="mt-2" onClick={() => void onRetry()} size="sm" variant="outline">
                  <RefreshCw aria-hidden="true" /> Обновить
                </Button>
              ) : null}
            </AlertContent>
          </Alert>
        ) : null}

        {canManage && state.status === 'ready' ? (
          <>
            <ul className="divide-y divide-border" aria-label="Активные сессии">
              {state.sessions.map((session) => (
                <SessionRow
                  actionPending={
                    pendingKey ===
                    actionKey(
                      session.isCurrent
                        ? { kind: 'current', sessionId: session.sessionId }
                        : { kind: 'other', sessionId: session.sessionId },
                    )
                  }
                  key={session.sessionId}
                  onRequestEnd={(intent, deviceName) => void requestEnd(intent, deviceName)}
                  session={session}
                />
              ))}
            </ul>
            <div className="mt-3 border-t border-border pt-3">
              <Button
                disabled={pendingKey !== null}
                onClick={() => void requestEnd({ kind: 'all' }, 'Все устройства')}
                size="sm"
                variant="destructive"
              >
                <LogOut aria-hidden="true" /> Выйти на всех устройствах
              </Button>
            </div>
          </>
        ) : null}

        {actionError ? (
          <Alert className="mt-3" role="alert" tone="danger">
            <AlertTriangle aria-hidden="true" />
            <AlertContent>
              <AlertTitle>Сессия не изменена</AlertTitle>
              <AlertDescription>{actionError}</AlertDescription>
            </AlertContent>
          </Alert>
        ) : null}
      </CardContent>

      {preparedEnd ? (
        <Dialog
          onOpenChange={(open) => {
            if (!open && !endingKey) setPreparedEnd(null)
          }}
          open
        >
          <DialogContent showCloseButton={false}>
            <>
              <DialogHeader>
                <DialogTitle>{confirmationTitle(preparedEnd.intent)}</DialogTitle>
                <DialogDescription>{confirmationDescription(preparedEnd)}</DialogDescription>
              </DialogHeader>
              {offlineWorkWarning(preparedEnd.offlineWork) ? (
                <Alert role="alert" tone="warning">
                  <AlertTriangle aria-hidden="true" />
                  <AlertContent>
                    <AlertTitle>Сначала проверьте очередь</AlertTitle>
                    <AlertDescription>
                      {offlineWorkWarning(preparedEnd.offlineWork)}
                    </AlertDescription>
                  </AlertContent>
                </Alert>
              ) : null}
              <DialogFooter>
                <Button
                  disabled={endingKey !== null}
                  onClick={() => setPreparedEnd(null)}
                  variant="outline"
                >
                  Отмена
                </Button>
                <Button
                  disabled={endingKey !== null}
                  onClick={() => void confirmEnd()}
                  variant="destructive"
                >
                  {endingKey ? <LoaderCircle aria-hidden="true" className="animate-spin" /> : null}
                  {endingKey ? 'Завершаем…' : 'Подтвердить'}
                </Button>
              </DialogFooter>
            </>
          </DialogContent>
        </Dialog>
      ) : null}
    </Card>
  )
}

export interface AccountSessionManagerProps {
  offlineWorkGuard?: SessionOfflineWorkGuard
  title?: string
}

/** Connects the reusable view to the real audience-relative auth API. */
export function AccountSessionManager({ offlineWorkGuard, title }: AccountSessionManagerProps) {
  const authentication = useAuthentication()
  const queryClient = useQueryClient()
  const principal = authenticationStatePrincipal(authentication.state)
  const authenticated = principal !== null
  const accountId = principal?.accountId ?? 'unavailable'
  const queryKey = useMemo(
    () => authQueryKeys.sessions({ audience: authentication.audience, accountId }),
    [accountId, authentication.audience],
  )
  const sessionsQuery = useQuery({
    enabled: authenticated,
    queryFn: ({ signal }) => authentication.client.sessions({ signal }),
    queryKey,
    retry: false,
  })

  useEffect(() => {
    if (sessionsQuery.error) authentication.handleApiError(sessionsQuery.error)
  }, [authentication, sessionsQuery.error])

  const endSession = useCallback(
    async (intent: SessionEndIntent) => {
      if (intent.kind === 'all') {
        await authentication.logoutAll()
        return
      }
      if (intent.kind === 'current') {
        await authentication.logout()
        return
      }

      await authentication.client.revokeSession(intent.sessionId)
      queryClient.setQueryData<AuthSessionsResponse>(queryKey, (current) =>
        current
          ? {
              ...current,
              sessions: current.sessions.filter(
                (session) => session.sessionId !== intent.sessionId,
              ),
            }
          : current,
      )
      await queryClient.invalidateQueries({ queryKey })
    },
    [authentication, queryClient, queryKey],
  )

  let state: SessionManagementLoadState
  if (!authenticated) {
    state = { status: 'error', kind: 'invalid' }
  } else if (sessionsQuery.isPending) {
    state = { status: 'loading' }
  } else if (sessionsQuery.error) {
    state = {
      status: 'error',
      kind:
        sessionsQuery.error instanceof AuthNetworkError
          ? 'network'
          : sessionsQuery.error instanceof AuthProtocolError
            ? 'invalid'
            : 'other',
    }
  } else if (sessionsQuery.data) {
    state = { status: 'ready', sessions: sessionsQuery.data.sessions }
  } else {
    state = { status: 'error', kind: 'invalid' }
  }

  return (
    <SessionManagementView
      {...(offlineWorkGuard === undefined ? {} : { offlineWorkGuard })}
      onEndSession={endSession}
      onRetry={async () => {
        await sessionsQuery.refetch()
      }}
      state={state}
      {...(title === undefined ? {} : { title })}
    />
  )
}
