import { useCallback, useEffect, useRef, useState } from 'react'

/** docs/runtime-isolation.md: a stale update notice must still reload the current URL.
 * Register listeners before looking up the worker: another tab can activate it meanwhile.
 */
export function activatePwaUpdate({
  container,
  href,
  signal,
  timeoutMs = 12_000,
}: {
  container: ServiceWorkerContainer
  href: string
  signal: AbortSignal
  timeoutMs?: number
}): Promise<void> {
  return new Promise((resolve, reject) => {
    const initialController = container.controller
    let registration: ServiceWorkerRegistration | undefined
    let requestedWorker: ServiceWorker | undefined
    let finished = false
    const watched = new Set<ServiceWorker>()
    const finish = (error?: Error) => {
      if (finished) return
      finished = true
      clearTimeout(timer)
      container.removeEventListener('controllerchange', check)
      registration?.removeEventListener('updatefound', check)
      watched.forEach((worker) => worker.removeEventListener('statechange', check))
      signal.removeEventListener('abort', abort)
      if (error) reject(error)
      else resolve()
    }
    const abort = () => finish(new Error('Update activation cancelled'))
    const watch = (worker: ServiceWorker | null) => {
      if (!worker || watched.has(worker)) return
      watched.add(worker)
      worker.addEventListener('statechange', check)
    }
    const check = () => {
      if (finished) return
      if (container.controller && container.controller !== initialController) {
        finish()
        return
      }
      if (!registration) return
      watch(registration.waiting)
      watch(registration.installing)
      watch(registration.active)
      if (registration.waiting) {
        const worker = registration.waiting
        if (worker.state === 'installed' && worker !== requestedWorker) {
          requestedWorker = worker
          try {
            worker.postMessage({ type: 'SKIP_WAITING' })
          } catch (error) {
            finish(error instanceof Error ? error : new Error('Activation message failed'))
          }
        }
        return
      }
      if (registration.installing) return
      if (requestedWorker?.state === 'redundant') {
        finish(new Error('Waiting worker became redundant'))
        return
      }
      // Another tab may already have activated the update before this click.
      // Workbox's messageSkipWaiting silently does nothing in that case.
      if (!requestedWorker && registration.active?.state === 'activated') finish()
    }
    const timer = setTimeout(() => finish(new Error('Update activation timed out')), timeoutMs)
    if (signal.aborted) {
      abort()
      return
    }
    signal.addEventListener('abort', abort, { once: true })
    container.addEventListener('controllerchange', check)
    void container.getRegistration(href).then(
      (value) => {
        if (finished) return
        registration = value
        if (!registration) {
          finish(new Error('No service worker registration'))
          return
        }
        registration.addEventListener('updatefound', check)
        check()
      },
      (error: unknown) => finish(error instanceof Error ? error : new Error('Registration failed')),
    )
  })
}

export function usePwaUpdateActivation() {
  const attempt = useRef<AbortController | null>(null)
  const reloading = useRef(false)
  const [applying, setApplying] = useState(false)
  const [error, setError] = useState(false)
  useEffect(() => () => attempt.current?.abort(), [])
  const applyUpdate = useCallback(async () => {
    if (attempt.current || reloading.current) return
    const controller = new AbortController()
    attempt.current = controller
    setApplying(true)
    setError(false)
    try {
      if (!navigator.serviceWorker) throw new Error('Service workers unavailable')
      await activatePwaUpdate({
        container: navigator.serviceWorker,
        href: window.location.href,
        signal: controller.signal,
      })
      if (controller.signal.aborted) return
      reloading.current = true
      window.location.reload()
    } catch {
      if (!controller.signal.aborted) setError(true)
    } finally {
      attempt.current = null
      if (!controller.signal.aborted) setApplying(false)
    }
  }, [])
  return { applyUpdate, applying, error }
}
