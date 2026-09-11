import type { AnyRouter } from '@tanstack/react-router'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useRegisterSW } from 'virtual:pwa-register/react'

import { Button } from '@vmsh/ui'
import { usePwaUpdateActivation } from '@vmsh/app-shell'

export function PwaUpdateController({ router }: { router: AnyRouter }) {
  const { applyUpdate, applying, error } = usePwaUpdateActivation()
  const updatePending = useRef(false)
  const detectedAtHref = useRef<string | undefined>(undefined)
  const [noticeHidden, setNoticeHidden] = useState(false)
  const {
    needRefresh: [needRefresh],
    offlineReady: [offlineReady, setOfflineReady],
  } = useRegisterSW({ immediate: true, onNeedReload: () => undefined })

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
      {error ? (
        <p role="alert" className="mt-2 text-sm text-destructive">
          Не удалось применить обновление. Попробуйте ещё раз.
        </p>
      ) : null}
      <div className="mt-3 flex gap-2">
        {showUpdateNotice ? (
          <Button
            size="sm"
            disabled={applying}
            onClick={() => {
              void applyUpdate()
            }}
          >
            {applying ? 'Обновляем…' : 'Обновить сейчас'}
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
