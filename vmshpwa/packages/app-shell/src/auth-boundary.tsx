import { LockKeyhole, TriangleAlert, WifiOff } from 'lucide-react'
import { useEffect, useRef, type ReactNode } from 'react'

import { staffCapabilitySchema, type StaffCapability } from '@vmsh/contracts'
import { Button, Card, CardContent } from '@vmsh/ui'

import { authenticationStatePrincipal, useAuthentication } from './auth-context'
import { AppStartupScreen } from './runtime-bootstrap'

export interface AuthenticationBoundaryProps {
  children: ReactNode
  checkingFallback?: ReactNode
  unauthenticatedFallback?: ReactNode
  offlineFallback?: ReactNode | ((retry: () => Promise<void>) => ReactNode)
  errorFallback?: ReactNode | ((error: unknown, retry: () => Promise<void>) => ReactNode)
}

/** Never mounts protected children before the server-authenticated state exists. */
export function AuthenticationBoundary({
  children,
  checkingFallback,
  unauthenticatedFallback,
  offlineFallback,
  errorFallback,
}: AuthenticationBoundaryProps) {
  const authentication = useAuthentication()
  const { state } = authentication
  const retry = () => authentication.retry()

  if (state.status === 'authenticated') return children
  if (state.status === 'checking') {
    return (
      checkingFallback ?? (
        <AppStartupScreen
          description="Проверяем действующую сессию на этом устройстве."
          state="loading"
          title="Проверяем вход"
        />
      )
    )
  }
  if (state.status === 'unauthenticated') {
    return (
      unauthenticatedFallback ?? (
        <AuthBoundaryPanel
          description="Чтобы открыть этот раздел, войдите в свой кабинет."
          icon={<LockKeyhole aria-hidden="true" />}
          title="Требуется вход"
        />
      )
    )
  }
  if (state.status === 'offline-unverified') {
    if (state.context && state.principal) return children
    return typeof offlineFallback === 'function'
      ? offlineFallback(retry)
      : (offlineFallback ?? (
          <AuthBoundaryPanel
            actionLabel="Повторить"
            description="Без связи сервер не может подтвердить сессию. Защищённые данные пока не открыты."
            icon={<WifiOff aria-hidden="true" />}
            onAction={() => void retry()}
            title="Не удалось проверить вход"
          />
        ))
  }
  return typeof errorFallback === 'function'
    ? errorFallback(state.error, retry)
    : (errorFallback ?? (
        <AuthBoundaryPanel
          actionLabel="Повторить"
          description="Ответ сервера не прошёл безопасную проверку. Защищённые данные не открыты."
          icon={<TriangleAlert aria-hidden="true" />}
          onAction={() => void retry()}
          title="Не удалось безопасно открыть кабинет"
          tone="danger"
        />
      ))
}

export function AuthenticationRedirectBoundary({
  children,
  onAuthenticationRequired,
}: {
  children: ReactNode
  onAuthenticationRequired: () => void
}) {
  const { state } = useAuthentication()
  const redirectRequested = useRef(false)

  useEffect(() => {
    if (state.status !== 'unauthenticated') {
      redirectRequested.current = false
      return
    }
    if (redirectRequested.current) return
    redirectRequested.current = true
    onAuthenticationRequired()
  }, [onAuthenticationRequired, state.status])

  return (
    <AuthenticationBoundary
      unauthenticatedFallback={
        <AppStartupScreen
          description="Открываем страницу входа и сохраним адрес этого раздела."
          state="loading"
          title="Требуется вход"
        />
      }
    >
      {children}
    </AuthenticationBoundary>
  )
}

export interface StaffCapabilityBoundaryProps {
  capability: StaffCapability
  children: ReactNode
  forbiddenFallback?: ReactNode
}

/**
 * UI capability gate only; backend object authorization remains mandatory.
 * Direct Staff routes will compose this with their server request in Phase 1.
 */
export function StaffCapabilityBoundary({
  capability,
  children,
  forbiddenFallback,
}: StaffCapabilityBoundaryProps) {
  const { state } = useAuthentication()
  const principal = authenticationStatePrincipal(state)
  if (!principal) return null
  const parsedCapability = staffCapabilitySchema.parse(capability)
  const permitted =
    principal.audience === 'staff' && principal.capabilities.includes(parsedCapability)
  if (permitted) return children
  return (
    forbiddenFallback ?? (
      <AuthBoundaryPanel
        description="У вашей учётной записи нет права открывать этот раздел."
        icon={<LockKeyhole aria-hidden="true" />}
        title="Нет доступа"
      />
    )
  )
}

function AuthBoundaryPanel({
  title,
  description,
  icon,
  tone = 'neutral',
  actionLabel,
  onAction,
}: {
  title: string
  description: string
  icon: ReactNode
  tone?: 'neutral' | 'danger'
  actionLabel?: string
  onAction?: () => void
}) {
  return (
    <main className="grid min-h-svh place-items-center bg-background p-4 text-foreground">
      <Card className="w-full max-w-md">
        <CardContent
          className="flex items-start gap-3 pt-6"
          role={tone === 'danger' ? 'alert' : 'status'}
        >
          <span className={tone === 'danger' ? 'text-status-danger' : 'text-muted-foreground'}>
            {icon}
          </span>
          <div className="min-w-0">
            <h1 className="font-medium">{title}</h1>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">{description}</p>
            {actionLabel && onAction ? (
              <Button className="mt-4" onClick={onAction} size="sm" type="button">
                {actionLabel}
              </Button>
            ) : null}
          </div>
        </CardContent>
      </Card>
    </main>
  )
}
