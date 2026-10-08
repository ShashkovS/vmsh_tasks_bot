import { t } from '@lingui/core/macro'
import { useEffect, useRef, useSyncExternalStore } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import {
  serviceAvailabilitySnapshot,
  subscribeServiceAvailability,
  setServiceUnconfirmedMessage,
  type ServiceAvailability,
} from '@vmsh/contracts'
import { resyncActiveQueries } from './query-resync'

export function useServiceAvailability() {
  return useSyncExternalStore(
    subscribeServiceAvailability,
    serviceAvailabilitySnapshot,
    serviceAvailabilitySnapshot,
  )
}
function subscribeBrowserOnline(listener: () => void) {
  window.addEventListener('online', listener)
  window.addEventListener('offline', listener)
  return () => {
    window.removeEventListener('online', listener)
    window.removeEventListener('offline', listener)
  }
}
/** docs/service-failure-copy-20261004.md: only browser offline proves no local network. */
export function useBrowserOnline() {
  return useSyncExternalStore(
    subscribeBrowserOnline,
    () => typeof navigator === 'undefined' || navigator.onLine !== false,
    () => true,
  )
}
export function serviceUnavailableText() {
  return t`Проблема на нашей стороне. Попробуйте позже.`
}
export function connectionFailureText(online: boolean) {
  return online
    ? t`Не получили ответ от сервера. Попробуйте позже.`
    : t`Нет подключения к интернету. Повторите попытку, когда связь появится.`
}
export function serviceAvailabilityTitle(state: ServiceAvailability, online = true) {
  if (!online) return t`Нет подключения к интернету`
  if (state.state === 'updating') return t`Обновляем сервис`
  return state.cause === 'server' ? t`Сервис временно недоступен` : t`Сервер не отвечает`
}
export function serviceWaitingText(state: ServiceAvailability) {
  if (state.state !== 'updating' && state.cause === 'server')
    return state.prolonged
      ? t`Проблема на нашей стороне всё ещё сохраняется. Проверяем доступность автоматически.`
      : t`Проблема на нашей стороне. Проверяем доступность автоматически.`
  if (state.prolonged)
    return state.state === 'updating'
      ? t`Обновление занимает больше времени. Мы продолжаем подключаться.`
      : t`Подключение занимает больше времени. Мы продолжаем пробовать.`
  return state.state === 'updating'
    ? t`Кабинет продолжит работу автоматически. Отправим после обновления.`
    : t`Пробуем подключиться автоматически. Можно продолжать работу с черновиком.`
}

/** docs/smooth-redeploy.md: never replace mounted editors with a startup gate. */
export function ServiceAvailabilityBanner() {
  const state = useServiceAvailability()
  const online = useBrowserOnline()
  const client = useQueryClient()
  const previous = useRef(state.state)
  useEffect(() => {
    setServiceUnconfirmedMessage(
      () =>
        t`Сервер не подтвердил действие. Проверьте результат перед повтором; черновик не нужно удалять.`,
    )
    return () => setServiceUnconfirmedMessage(undefined)
  }, [])
  useEffect(() => {
    if (previous.current !== 'ready' && state.state === 'ready') void resyncActiveQueries(client)
    previous.current = state.state
  }, [client, state.state])
  return <ServiceAvailabilityBannerView state={state} online={online} />
}

export function ServiceAvailabilityBannerView({
  state,
  online = true,
}: {
  state: ServiceAvailability
  online?: boolean
}) {
  if (state.state === 'ready') return null
  return (
    <div
      role="status"
      aria-live="polite"
      className="border-b bg-surface-subtle px-4 py-2 text-small text-foreground"
    >
      <span className="font-medium">{serviceAvailabilityTitle(state, online)}. </span>
      {online ? serviceWaitingText(state) : connectionFailureText(false)}
    </div>
  )
}
