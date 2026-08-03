import { useCallback, useEffect, useState } from 'react'

import type { NotificationClient } from './notification-client'
import { browserPushSubscriptionRequest, decodeApplicationServerKey } from './push-browser'

export type PushDeviceState =
  'loading' | 'available' | 'enabled' | 'dismissed' | 'denied' | 'unsupported' | 'error'

function browserPushSupported(): boolean {
  return (
    typeof Notification !== 'undefined' &&
    typeof navigator !== 'undefined' &&
    'serviceWorker' in navigator &&
    typeof PushManager !== 'undefined'
  )
}

/**
 * Owns the browser/server subscription handshake shared by Student and Family.
 * Product copy and layout stay in PushDeviceControls; see Phase 8 notification UX.
 */
export function usePushDevice({
  applicationServerKey,
  client,
}: {
  applicationServerKey: string
  client: NotificationClient
}) {
  const [state, setState] = useState<PushDeviceState>(() =>
    browserPushSupported() ? 'loading' : 'unsupported',
  )

  useEffect(() => {
    let cancelled = false
    if (!browserPushSupported()) return
    void navigator.serviceWorker.ready
      .then((registration) => registration.pushManager.getSubscription())
      .then(async (subscription) => {
        if (cancelled) return
        if (subscription) {
          await client.savePushSubscription(browserPushSubscriptionRequest(subscription))
          if (!cancelled) setState('enabled')
          return
        }
        setState(Notification.permission === 'denied' ? 'denied' : 'available')
      })
      .catch(() => {
        if (!cancelled) setState('error')
      })
    return () => {
      cancelled = true
    }
  }, [client])

  const enable = useCallback(async () => {
    try {
      const permission = await Notification.requestPermission()
      if (permission !== 'granted') {
        setState(permission === 'denied' ? 'denied' : 'available')
        return
      }
      const registration = await navigator.serviceWorker.ready
      const existing = await registration.pushManager.getSubscription()
      const subscription =
        existing ??
        (await registration.pushManager.subscribe({
          applicationServerKey: decodeApplicationServerKey(applicationServerKey),
          userVisibleOnly: true,
        }))
      await client.savePushSubscription(browserPushSubscriptionRequest(subscription))
      setState('enabled')
    } catch {
      setState('error')
    }
  }, [applicationServerKey, client])

  const disable = useCallback(async () => {
    try {
      const registration = await navigator.serviceWorker.ready
      const subscription = await registration.pushManager.getSubscription()
      if (subscription) {
        await client.deletePushSubscription(subscription.endpoint)
        await subscription.unsubscribe()
      }
      setState('available')
    } catch {
      setState('error')
    }
  }, [client])

  const dismiss = useCallback(() => setState('dismissed'), [])

  return {
    state,
    dismiss,
    enable,
    disable,
  }
}
