import { useRegisterSW } from 'virtual:pwa-register/react'

import { Button } from '@vmsh/ui'

export function PwaUpdateController() {
  const {
    needRefresh: [needRefresh, setNeedRefresh],
    offlineReady: [offlineReady, setOfflineReady],
    updateServiceWorker,
  } = useRegisterSW({ immediate: true })

  if (!needRefresh && !offlineReady) return null

  return (
    <div
      className="fixed right-3 bottom-20 z-50 max-w-sm rounded-md border bg-background p-4 shadow-lg md:bottom-3"
      role="status"
      data-testid="pwa-update-state"
    >
      <p className="text-sm font-medium">
        {needRefresh ? 'Доступно обновление приложения' : 'Приложение готово к работе без сети'}
      </p>
      <div className="mt-3 flex gap-2">
        {needRefresh ? (
          <Button size="sm" onClick={() => void updateServiceWorker(true)}>
            Обновить
          </Button>
        ) : null}
        <Button
          size="sm"
          variant="ghost"
          onClick={() => {
            setNeedRefresh(false)
            setOfflineReady(false)
          }}
        >
          Закрыть
        </Button>
      </div>
    </div>
  )
}
