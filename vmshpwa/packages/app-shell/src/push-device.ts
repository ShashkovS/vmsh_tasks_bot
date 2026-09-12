import { useCallback, useEffect, useRef, useState } from 'react'

import type { NotificationClient } from './notification-client'
import { browserPushSubscriptionRequest, decodeApplicationServerKey } from './push-browser'

export type PushDeviceState =
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

export function browserPushAvailability(): 'available' | 'unsupported' | 'install-required' {
  if (typeof navigator === 'undefined') return 'unsupported'
  const ios =
    /iPad|iPhone|iPod/.test(navigator.userAgent) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
  const standalone =
    window.matchMedia?.('(display-mode: standalone)').matches ||
    ('standalone' in navigator && navigator.standalone === true)
  if (ios && !standalone) return 'install-required'
  return typeof Notification !== 'undefined' &&
    'serviceWorker' in navigator &&
    typeof PushManager !== 'undefined'
    ? 'available'
    : 'unsupported'
}

async function readyRegistration(): Promise<ServiceWorkerRegistration> {
  let timer: ReturnType<typeof setTimeout> | undefined
  try {
    return await Promise.race([
      navigator.serviceWorker.ready,
      new Promise<never>((_resolve, reject) => {
        timer = setTimeout(() => reject(new Error('Service worker not ready')), 10_000)
      }),
    ])
  } finally {
    clearTimeout(timer)
  }
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
  const [state, setState] = useState<PushDeviceState>(() => {
    const availability = browserPushAvailability()
    return availability === 'available' ? 'loading' : availability
  })
  const clientRef = useRef(client)
  useEffect(() => {
    clientRef.current = client
  }, [client])
  const busy = useRef(false)
  const generation = useRef(0)

  useEffect(() => {
    const reconcile = async () => {
      if (busy.current || browserPushAvailability() !== 'available') return
      const current = ++generation.current
      try {
        const registration = await readyRegistration()
        const subscription = await registration.pushManager.getSubscription()
        if (current !== generation.current) return
        if (subscription && Notification.permission === 'granted') {
          await clientRef.current.savePushSubscription(browserPushSubscriptionRequest(subscription))
          if (current === generation.current) setState('enabled')
        } else if (current === generation.current) {
          setState(Notification.permission === 'denied' ? 'denied' : 'available')
        }
      } catch {
        if (current === generation.current) setState('error')
      }
    }
    void reconcile()
    const onFocus = () => {
      void reconcile()
    }
    window.addEventListener('focus', onFocus)
    window.addEventListener('online', onFocus)
    return () => {
      generation.current += 1
      window.removeEventListener('focus', onFocus)
      window.removeEventListener('online', onFocus)
    }
  }, [])

  const enable = useCallback(async () => {
    if (busy.current || browserPushAvailability() !== 'available') return
    busy.current = true
    const current = ++generation.current
    setState('enabling')
    try {
      // Keep the system prompt in the click gesture (especially Safari).
      const permission =
        Notification.permission === 'granted' ? 'granted' : await Notification.requestPermission()
      if (current !== generation.current) return
      if (permission !== 'granted') {
        setState(permission === 'denied' ? 'denied' : 'available')
        return
      }
      const registration = await readyRegistration()
      if (current !== generation.current) return
      const existing = await registration.pushManager.getSubscription()
      if (current !== generation.current) return
      const subscription =
        existing ??
        (await registration.pushManager.subscribe({
          applicationServerKey: decodeApplicationServerKey(applicationServerKey),
          userVisibleOnly: true,
        }))
      if (current !== generation.current) return
      await client.savePushSubscription(browserPushSubscriptionRequest(subscription))
      if (current === generation.current) setState('enabled')
    } catch {
      if (current === generation.current) setState('error')
    } finally {
      busy.current = false
    }
  }, [applicationServerKey, client])

  const disable = useCallback(async () => {
    if (busy.current || browserPushAvailability() !== 'available') return
    busy.current = true
    const current = ++generation.current
    setState('disabling')
    try {
      const registration = await readyRegistration()
      const subscription = await registration.pushManager.getSubscription()
      if (subscription) {
        await client.deletePushSubscription(subscription.endpoint)
        await subscription.unsubscribe()
      }
      if (current === generation.current) setState('available')
    } catch {
      if (current === generation.current) setState('error')
    } finally {
      busy.current = false
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
