import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { BellOff } from 'lucide-react'

import {
  Alert,
  AlertContent,
  AlertDescription,
  AlertTitle,
  Button,
  Card,
  CardContent,
} from '@vmsh/ui'

import { PushPermissionCard, type PushCategory } from './push-permission-card'

export type PushDeviceControlState =
  | 'loading'
  | 'available'
  | 'enabled'
  | 'dismissed'
  | 'denied'
  | 'unsupported'
  | 'error'
  | 'enabling'
  | 'disabling'
  | 'install-required'

/** Presentation for the shared Student/Family browser subscription handshake. */
export function PushDeviceControls({
  categories,
  onDisable,
  onDismiss,
  onEnable,
  state,
}: {
  categories: PushCategory[]
  onDisable: () => void
  onDismiss: () => void
  onEnable: () => void
  state: PushDeviceControlState
}) {
  if (state === 'enabling' || state === 'disabling')
    return (
      <p role="status" className="text-small text-muted-foreground">
        {state === 'enabling' ? t`Включаем уведомления…` : t`Отключаем уведомления…`}
      </p>
    )
  if (state === 'install-required')
    return (
      <Alert>
        <BellOff aria-hidden="true" />
        <AlertContent>
          <AlertTitle><Trans>Уведомления на iPhone и iPad</Trans></AlertTitle>
          <AlertDescription>
            <Trans>Добавьте кабинет на экран «Домой» через меню браузера и откройте его с появившегося
            значка. После этого здесь можно включить уведомления.</Trans>
          </AlertDescription>
        </AlertContent>
      </Alert>
    )
  if (state === 'loading') {
    return <p className="text-small text-muted-foreground"><Trans>Проверяем это устройство…</Trans></p>
  }
  if (state === 'available') {
    return <PushPermissionCard categories={categories} onDismiss={onDismiss} onEnable={onEnable} />
  }
  if (state === 'dismissed') return null
  if (state === 'enabled') {
    return (
      <Card>
        <CardContent className="flex items-center justify-between gap-4 py-4">
          <div>
            <p className="text-small font-medium"><Trans>Push включены на этом устройстве</Trans></p>
            <p className="text-caption text-muted-foreground"><Trans>Категории можно настроить ниже.</Trans></p>
          </div>
          <Button onClick={onDisable} size="sm" variant="outline">
            <Trans>Отключить</Trans>
          </Button>
        </CardContent>
      </Card>
    )
  }
  return (
    <Alert tone={state === 'denied' ? 'neutral' : 'warning'}>
      <BellOff aria-hidden="true" />
      <AlertContent>
        <AlertTitle>
          {state === 'denied'
            ? t`Push запрещены в браузере`
            : state === 'unsupported'
              ? t`Push не поддерживаются`
              : t`Не удалось настроить push`}
        </AlertTitle>
        <AlertDescription>
          {state === 'denied'
            ? t`Разрешение можно вернуть в настройках сайта.`
            : state === 'unsupported'
              ? t`Все события всё равно останутся в приложении.`
              : t`Проверьте соединение и попробуйте ещё раз.`}
        </AlertDescription>
        {state === 'denied' ? (
          <div className="mt-3 space-y-3 text-small">
            <p><Trans>Кабинет не может отменить запрет браузера. Разрешите уведомления вручную:</Trans></p>
            <ul className="list-disc space-y-2 pl-5">
              <li>
                <Trans><strong>Chrome и Edge:</strong> нажмите значок слева от адреса сайта → «Настройки
                сайта» или «Разрешения» → «Уведомления» → «Разрешить».</Trans>
              </li>
              <li>
                <Trans><strong>Firefox:</strong> откройте настройки браузера → «Приватность и защита» →
                «Разрешения» → «Уведомления» → «Параметры». Найдите этот сайт и разрешите
                уведомления.</Trans>
              </li>
              <li>
                <Trans><strong>Safari на Mac:</strong> Safari → «Настройки» → «Веб-сайты» → «Уведомления».
                Для этого сайта выберите «Разрешить».</Trans>
              </li>
              <li>
                <Trans><strong>iPhone и iPad:</strong> откройте системные «Настройки» → «Уведомления» →
                кабинет ВМШ → «Допуск уведомлений». Кабинет должен быть добавлен на экран «Домой».</Trans>
              </li>
            </ul>
            <p>
              <Trans>После изменения вернитесь сюда и нажмите «Включить уведомления». Если кнопка не
              появилась, обновите страницу. Также проверьте, разрешены ли уведомления для браузера в
              настройках устройства.</Trans>
            </p>
          </div>
        ) : null}
        {state === 'error' ? (
          <Button onClick={onEnable} size="sm" variant="outline">
            <Trans>Включить уведомления</Trans>
          </Button>
        ) : null}
      </AlertContent>
    </Alert>
  )
}
