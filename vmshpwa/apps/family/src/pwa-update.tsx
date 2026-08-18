import type { AnyRouter } from '@tanstack/react-router'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useRegisterSW } from 'virtual:pwa-register/react'

import { Button } from '@vmsh/ui'

export function PwaUpdateController({ router }: { router: AnyRouter }) {
  const applyInProgress = useRef(false)
  const activationRequested = useRef(false)
  const updatePending = useRef(false)
  const detectedAtHref = useRef<string | undefined>(undefined)
  const reloadStarted = useRef(false)
  const [noticeHidden, setNoticeHidden] = useState(false)
  const reloadAfterControllerChange = useCallback(() => {
    if (!activationRequested.current || reloadStarted.current) return
    reloadStarted.current = true
    window.location.reload()
  }, [])
  const {
    needRefresh: [needRefresh],
    offlineReady: [offlineReady, setOfflineReady],
    updateServiceWorker,
  } = useRegisterSW({ immediate: true, onNeedReload: reloadAfterControllerChange })
  const applyUpdate = useCallback(async () => {
    if (applyInProgress.current) return
    applyInProgress.current = true
    activationRequested.current = true
    try {
      const registration = await navigator.serviceWorker?.getRegistration(window.location.href)
      if (registration?.waiting) {
        registration.waiting.postMessage({ type: 'SKIP_WAITING' })
        return
      }
      await updateServiceWorker(false)
    } catch {
      activationRequested.current = false
    } finally {
      applyInProgress.current = false
    }
  }, [updateServiceWorker])

  const applyAtSafeMoment = useCallback(() => {
    if (!updatePending.current || !navigator.onLine) return
    void applyUpdate()
  }, [applyUpdate])

  useEffect(() => {
    if (!needRefresh) return
    updatePending.current = true
    detectedAtHref.current = router.latestLocation.href
  }, [needRefresh, router])

  useEffect(
    () =>
      router.subscribe('onResolved', (event) => {
        if (event.hrefChanged && event.toLocation.href !== detectedAtHref.current) {
          applyAtSafeMoment()
        }
      }),
    [applyAtSafeMoment, router],
  )

  useEffect(() => {
    navigator.serviceWorker?.addEventListener('controllerchange', reloadAfterControllerChange)
    return () =>
      navigator.serviceWorker?.removeEventListener('controllerchange', reloadAfterControllerChange)
  }, [reloadAfterControllerChange])

  const showUpdateNotice = needRefresh && !noticeHidden
  if (!showUpdateNotice && !offlineReady) return null

  return (
    <div
      className="fixed right-3 bottom-20 z-50 max-w-sm rounded-md border bg-background p-4 shadow-lg md:bottom-3"
      role="status"
      data-testid="pwa-update-state"
    >
      <p className="text-sm font-medium">
        {showUpdateNotice ? 'Доступно обновление.' : 'Приложение готово к работе без сети'}
      </p>
      <div className="mt-3 flex gap-2">
        {showUpdateNotice ? (
          <Button
            size="sm"
            onClick={() => {
              void applyUpdate()
            }}
          >
            Обновить сейчас
          </Button>
        ) : null}
        <Button
          size="sm"
          variant="ghost"
          onClick={() => {
            if (showUpdateNotice) setNoticeHidden(true)
            else setOfflineReady(false)
          }}
        >
          {showUpdateNotice ? 'Скрыть' : 'Закрыть'}
        </Button>
      </div>
    </div>
  )
}
