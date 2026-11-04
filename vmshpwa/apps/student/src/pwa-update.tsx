import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import type { AnyRouter } from '@tanstack/react-router'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useRegisterSW } from 'virtual:pwa-register/react'

import { Button } from '@vmsh/ui'
import { usePwaUpdateActivation } from '@vmsh/app-shell'

import { safePwaUpdateEvent } from './pwa-update-events'

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

  useEffect(() => {
    window.addEventListener(safePwaUpdateEvent, applyAtSafeMoment)
    return () => window.removeEventListener(safePwaUpdateEvent, applyAtSafeMoment)
  }, [applyAtSafeMoment])

  const showUpdateNotice = needRefresh && !noticeHidden
  if (!showUpdateNotice && !offlineReady) return null

  return (
    <div
      className="fixed inset-x-3 bottom-[calc(4.5rem+env(safe-area-inset-bottom))] z-50 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-md border bg-background px-3 py-2 shadow-lg md:inset-x-auto md:right-3 md:bottom-3 md:max-w-sm md:p-4"
      role="status"
      data-testid="pwa-update-state"
    >
      <p className="text-sm font-medium">
        {showUpdateNotice ? t`Доступно обновление.` : t`Приложение готово к работе без сети`}
      </p>
      {error ? (
        <p role="alert" className="w-full text-sm text-destructive md:mt-2">
          <Trans>Не удалось применить обновление. Попробуйте ещё раз.</Trans>
        </p>
      ) : null}
      <div className="ml-auto flex gap-2 md:mt-2 md:ml-0">
        {showUpdateNotice ? (
          <Button
            size="sm"
            disabled={applying}
            onClick={() => {
              void applyUpdate()
            }}
          >
            {applying ? t`Обновляем…` : t`Обновить сейчас`}
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
          {showUpdateNotice ? t`Скрыть` : t`Закрыть`}
        </Button>
      </div>
    </div>
  )
}
