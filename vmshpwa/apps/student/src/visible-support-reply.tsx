import { useEffect, useRef, type ReactNode } from 'react'

/** docs/question-attention.md: actual answer visibility, never a GET/read side effect. */
export function VisibleSupportReply({
  entryId,
  unread,
  onRead,
  children,
}: {
  entryId: string
  unread: boolean
  onRead: (entryId: string) => Promise<unknown>
  children: ReactNode
}) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!unread || !ref.current) return
    const node = ref.current
    let timer: ReturnType<typeof setTimeout> | undefined
    let retry: ReturnType<typeof setTimeout> | undefined
    let stopped = false
    let pending = false
    let confirmed = false
    const cancel = () => {
      clearTimeout(timer)
      timer = undefined
      clearTimeout(retry)
      retry = undefined
    }
    const visible = () => {
      const rect = node.getBoundingClientRect()
      const height = Math.max(0, Math.min(rect.bottom, window.innerHeight) - Math.max(rect.top, 0))
      const width = Math.max(0, Math.min(rect.right, window.innerWidth) - Math.max(rect.left, 0))
      return (
        document.visibilityState === 'visible' &&
        navigator.onLine &&
        rect.height > 0 &&
        rect.width > 0 &&
        height >= 0.75 * Math.min(rect.height, window.innerHeight) &&
        width >= 0.75 * Math.min(rect.width, window.innerWidth)
      )
    }
    const update = () => {
      if (stopped || confirmed) return
      if (!visible()) {
        cancel()
        return
      }
      if (timer !== undefined || retry !== undefined || pending) return
      timer = setTimeout(() => {
        timer = undefined
        if (!visible() || stopped) return
        pending = true
        void onRead(entryId)
          .then(() => {
            confirmed = true
          })
          .catch(() => {
            // Retain attention on failure; retries still require fresh continuous visibility.
            if (!stopped && visible())
              retry = setTimeout(() => {
                retry = undefined
                update()
              }, 5_000)
          })
          .finally(() => {
            pending = false
          })
      }, 3_000)
    }
    const observer =
      typeof IntersectionObserver === 'undefined'
        ? undefined
        : new IntersectionObserver(update, { threshold: [0, 0.25, 0.5, 0.75, 1] })
    const resize = typeof ResizeObserver === 'undefined' ? undefined : new ResizeObserver(update)
    observer?.observe(node)
    resize?.observe(node)
    document.addEventListener('scroll', update, true)
    document.addEventListener('visibilitychange', update)
    window.addEventListener('resize', update)
    window.addEventListener('online', update)
    window.addEventListener('offline', update)
    update()
    return () => {
      stopped = true
      cancel()
      observer?.disconnect()
      resize?.disconnect()
      document.removeEventListener('scroll', update, true)
      document.removeEventListener('visibilitychange', update)
      window.removeEventListener('resize', update)
      window.removeEventListener('online', update)
      window.removeEventListener('offline', update)
    }
  }, [entryId, onRead, unread])
  return (
    <div ref={ref} className="scroll-mt-24" data-support-entry-id={entryId}>
      {children}
    </div>
  )
}
