import { useCallback, useEffect, useRef } from 'react'
import { useRegisterSW } from 'virtual:pwa-register/react'

import { Button } from '@vmsh/ui'

export function PwaUpdateController() {
  const applyRequested = useRef(false)
  const reloadStarted = useRef(false)
  const reloadAfterControllerChange = useCallback(() => {
    if (!applyRequested.current || reloadStarted.current) return
    reloadStarted.current = true
    window.location.reload()
  }, [])
  const {
    needRefresh: [needRefresh, setNeedRefresh],
    offlineReady: [offlineReady, setOfflineReady],
    updateServiceWorker,
  } = useRegisterSW({ immediate: true, onNeedReload: reloadAfterControllerChange })
  const applyUpdate = useCallback(async () => {
    applyRequested.current = true
    let registration: ServiceWorkerRegistration | undefined
    try {
      registration = await navigator.serviceWorker?.getRegistration(window.location.href)
    } catch {
      // Workbox retains the same browser registration fallback.
    }
    if (registration?.waiting) {
      // Address the browser-owned waiting worker directly.  Workbox Window can
      // retain an older wrapper across an app reload, while the registration
      // remains the authoritative update state.  Phase-0 runtime E2E proves
      // this path in Chromium, WebKit and Firefox.
      registration.waiting.postMessage({ type: 'SKIP_WAITING' })
      return
    }
    await updateServiceWorker(false)
  }, [updateServiceWorker])

  useEffect(() => {
    navigator.serviceWorker?.addEventListener('controllerchange', reloadAfterControllerChange)
    return () =>
      navigator.serviceWorker?.removeEventListener('controllerchange', reloadAfterControllerChange)
  }, [reloadAfterControllerChange])

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
          <Button
            size="sm"
            onClick={() => {
              void applyUpdate()
            }}
          >
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
