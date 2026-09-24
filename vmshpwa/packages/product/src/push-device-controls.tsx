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
        {state === 'enabling' ? 'Включаем уведомления…' : 'Отключаем уведомления…'}
      </p>
    )
  if (state === 'install-required')
    return (
      <Alert>
        <BellOff aria-hidden="true" />
        <AlertContent>
          <AlertTitle>Уведомления на iPhone и iPad</AlertTitle>
          <AlertDescription>
            Добавьте кабинет на экран «Домой» через меню браузера и откройте его с появившегося
            значка. После этого здесь можно включить уведомления.
          </AlertDescription>
        </AlertContent>
      </Alert>
    )
  if (state === 'loading') {
    return <p className="text-small text-muted-foreground">Проверяем это устройство…</p>
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
            <p className="text-small font-medium">Push включены на этом устройстве</p>
            <p className="text-caption text-muted-foreground">Категории можно настроить ниже.</p>
          </div>
          <Button onClick={onDisable} size="sm" variant="outline">
            Отключить
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
            ? 'Push запрещены в браузере'
            : state === 'unsupported'
              ? 'Push не поддерживаются'
              : 'Не удалось настроить push'}
        </AlertTitle>
        <AlertDescription>
          {state === 'denied'
            ? 'Разрешение можно вернуть в настройках сайта.'
            : state === 'unsupported'
              ? 'Все события всё равно останутся в приложении.'
              : 'Проверьте соединение и попробуйте ещё раз.'}
        </AlertDescription>
        {state === 'denied' ? (
          <div className="mt-3 space-y-3 text-small">
            <p>Кабинет не может отменить запрет браузера. Разрешите уведомления вручную:</p>
            <ul className="list-disc space-y-2 pl-5">
              <li>
                <strong>Chrome и Edge:</strong> нажмите значок слева от адреса сайта → «Настройки
                сайта» или «Разрешения» → «Уведомления» → «Разрешить».
              </li>
              <li>
                <strong>Firefox:</strong> откройте настройки браузера → «Приватность и защита» →
                «Разрешения» → «Уведомления» → «Параметры». Найдите этот сайт и разрешите
                уведомления.
              </li>
              <li>
                <strong>Safari на Mac:</strong> Safari → «Настройки» → «Веб-сайты» → «Уведомления».
                Для этого сайта выберите «Разрешить».
              </li>
              <li>
                <strong>iPhone и iPad:</strong> откройте системные «Настройки» → «Уведомления» →
                кабинет ВМШ → «Допуск уведомлений». Кабинет должен быть добавлен на экран «Домой».
              </li>
            </ul>
            <p>
              После изменения вернитесь сюда и нажмите «Включить уведомления». Если кнопка не
              появилась, обновите страницу. Также проверьте, разрешены ли уведомления для браузера в
              настройках устройства.
            </p>
          </div>
        ) : null}
        {state === 'error' ? (
          <Button onClick={onEnable} size="sm" variant="outline">
            Включить уведомления
          </Button>
        ) : null}
      </AlertContent>
    </Alert>
  )
}
