import { useMemo, useState } from 'react'
import { Bell } from 'lucide-react'
import { Button } from '@vmsh/ui'
import {
  createNotificationClient,
  usePushSubscriptionConfigQuery,
  type NotificationClient,
} from './notification-client'
import { useAuthentication } from './auth-context'
import { usePushDevice } from './push-device'

/** Account/application-scoped consent; see docs/notification-activation.md. */
export function PushOnboarding() {
  const authentication = useAuthentication()
  const state = authentication.state
  if (
    state.status !== 'authenticated' ||
    state.principal.audience === 'staff' ||
    (state.principal.audience === 'student' && state.principal.isStaffTesting)
  )
    return null
  return (
    <AuthenticatedPushOnboarding
      key={`${state.principal.audience}:${state.principal.accountId}`}
      audience={state.principal.audience}
      accountId={state.principal.accountId}
    />
  )
}

function AuthenticatedPushOnboarding({
  audience,
  accountId,
}: {
  audience: 'student' | 'family'
  accountId: string
}) {
  const authentication = useAuthentication()
  const client = useMemo(
    () =>
      createNotificationClient(authentication.client.runtime, audience, {
        refreshSession: () => authentication.refresh(),
      }),
    [authentication, audience],
  )
  const config = usePushSubscriptionConfigQuery(client, { audience, accountId })
  if (!config.data?.enabled || !config.data.applicationServerKey) return null
  const storageKey = `vmsh-push-invitation:${authentication.client.runtime.instance}:${audience}:${accountId}`
  return (
    <PushInvitation
      client={client}
      applicationServerKey={config.data.applicationServerKey}
      storageKey={storageKey}
      audience={audience}
    />
  )
}

export function PushInvitation({
  client,
  applicationServerKey,
  storageKey,
  audience,
}: {
  client: NotificationClient
  applicationServerKey: string
  storageKey: string
  audience: 'student' | 'family'
}) {
  const push = usePushDevice({ client, applicationServerKey })
  const [dismissed, setDismissed] = useState(() => {
    try {
      return localStorage.getItem(storageKey) === 'dismissed'
    } catch {
      return false
    }
  })
  const dismiss = () => {
    setDismissed(true)
    try {
      localStorage.setItem(storageKey, 'dismissed')
    } catch {
      /* In-memory dismissal still works. */
    }
  }
  if (
    dismissed ||
    ['loading', 'enabled', 'unsupported', 'denied', 'dismissed'].includes(push.state)
  )
    return null
  const installing = push.state === 'install-required'
  const enabling = push.state === 'enabling'
  return (
    <section
      aria-label="Уведомления"
      className="m-3 flex flex-wrap items-center gap-3 rounded-lg border border-border bg-surface p-3 text-small print:hidden"
    >
      <Bell aria-hidden="true" className="size-5 shrink-0 text-muted-foreground" />
      <div className="min-w-0 flex-1 basis-48">
        <p className="font-medium">
          {installing ? 'Уведомления на iPhone и iPad' : 'Включить уведомления?'}
        </p>
        <p className="text-muted-foreground">
          {installing
            ? 'Добавьте кабинет на экран «Домой» через меню браузера и откройте его с появившегося значка.'
            : push.state === 'error'
              ? 'Не удалось подключить устройство. Проверьте интернет и попробуйте ещё раз.'
              : audience === 'student'
                ? 'Результаты проверки, ответы преподавателей и новые материалы.'
                : 'Ответы организаторов, новости и новые материалы.'}
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        {!installing ? (
          <Button disabled={enabling} onClick={() => void push.enable()} size="sm">
            {enabling ? 'Включаем…' : 'Включить уведомления'}
          </Button>
        ) : null}
        <Button disabled={enabling} onClick={dismiss} size="sm" variant="ghost">
          Не сейчас
        </Button>
      </div>
    </section>
  )
}
