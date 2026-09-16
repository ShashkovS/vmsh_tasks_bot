import { useEffect, useRef, useSyncExternalStore } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import {
  serviceAvailabilitySnapshot,
  subscribeServiceAvailability,
  type ServiceAvailability,
} from '@vmsh/contracts'

export function useServiceAvailability() {
  return useSyncExternalStore(
    subscribeServiceAvailability,
    serviceAvailabilitySnapshot,
    serviceAvailabilitySnapshot,
  )
}
export function serviceWaitingText(state: ServiceAvailability) {
  if (state.prolonged)
    return state.state === 'updating'
      ? 'Обновление занимает больше времени. Мы продолжаем подключаться.'
      : 'Подключение занимает больше времени. Мы продолжаем пробовать.'
  return state.state === 'updating'
    ? 'Кабинет продолжит работу автоматически. Отправим после обновления.'
    : 'Пробуем подключиться автоматически. Можно продолжать работу с черновиком.'
}

/** docs/smooth-redeploy.md: never replace mounted editors with a startup gate. */
export function ServiceAvailabilityBanner() {
  const state = useServiceAvailability()
  const client = useQueryClient()
  const previous = useRef(state.state)
  useEffect(() => {
    if (previous.current !== 'ready' && state.state === 'ready')
      void client.invalidateQueries({ type: 'active' })
    previous.current = state.state
  }, [client, state.state])
  return <ServiceAvailabilityBannerView state={state} />
}

export function ServiceAvailabilityBannerView({ state }: { state: ServiceAvailability }) {
  if (state.state === 'ready') return null
  return (
    <div
      role="status"
      aria-live="polite"
      className="border-b bg-surface-subtle px-4 py-2 text-small text-foreground"
    >
      <span className="font-medium">
        {state.state === 'updating' ? 'Обновляем сервис. ' : 'Восстанавливаем соединение. '}
      </span>
      {serviceWaitingText(state)}
    </div>
  )
}
