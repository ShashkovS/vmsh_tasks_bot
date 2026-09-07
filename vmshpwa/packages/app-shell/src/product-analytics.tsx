import { useEffect, useMemo } from 'react'

import type { Audience } from '@vmsh/contracts'

import { useRuntimeConfig } from './runtime-bootstrap'

export type ProductEventType =
  | 'page.view'
  | 'task.open'
  | 'material.open'
  | 'test.submit'
  | 'written.submit'
  | 'photo.attach'
  | 'question.create'
  | 'question.reply'
  | 'group.change'
  | 'attendance.change'
  | 'notifications.change'
  | 'queue.open'
  | 'content.upload'
  | 'content.compile'
  | 'content.publish'
  | 'metadata.generate'
  | 'metadata.change'
  | 'review.verdict'
  | 'news.publish'
  | 'broadcast.publish'
  | 'schedule.change'
  | 'classroom.change'

type ProductEvent = {
  eventType: ProductEventType
  routeId: string
  entityType?: string
  entityId?: string
  viewportWidth: number
  viewportHeight: number
  devicePixelRatio: number
  pointerType: 'fine' | 'coarse' | 'none' | 'unknown'
  displayMode: 'browser' | 'standalone' | 'minimal-ui' | 'fullscreen'
}

const PRODUCT_ACTION_EVENT = 'vmsh:product-analytics-action'

export function recordProductAction(
  eventType: Exclude<ProductEventType, 'page.view'>,
  entity?: { type: string; id: string },
): void {
  if (typeof window === 'undefined') return
  window.dispatchEvent(new CustomEvent(PRODUCT_ACTION_EVENT, { detail: { eventType, entity } }))
}

function environment(): Omit<ProductEvent, 'eventType' | 'routeId' | 'entityType' | 'entityId'> {
  const media = (query: string) => window.matchMedia?.(query).matches ?? false
  const pointer = media('(pointer: fine)') ? 'fine' : media('(pointer: coarse)') ? 'coarse' : 'none'
  const displayMode = media('(display-mode: standalone)')
    ? 'standalone'
    : media('(display-mode: minimal-ui)')
      ? 'minimal-ui'
      : media('(display-mode: fullscreen)')
        ? 'fullscreen'
        : 'browser'
  return {
    viewportWidth: Math.max(0, Math.round(window.innerWidth)),
    viewportHeight: Math.max(0, Math.round(window.innerHeight)),
    devicePixelRatio: Math.max(0.1, Math.min(10, window.devicePixelRatio || 1)),
    pointerType: pointer,
    displayMode,
  }
}

/** Remove query/hash and opaque path segments before product telemetry leaves the browser. */
export function canonicalProductRoute(pathname: string): string {
  const segments = (pathname.split(/[?#]/, 1)[0] ?? '').split('/').filter(Boolean)
  if (segments.length === 0) return '/'
  return `/${segments
    .map((segment) => (/^[a-z]+$/.test(segment) ? segment : ':id'))
    .join('/')}`
}

export class ProductAnalyticsTracker {
  #events: ProductEvent[] = []
  #flushing = false

  constructor(
    private readonly audience: Audience,
    private readonly apiBase: string,
    private readonly fetchImplementation: typeof fetch = fetch,
  ) {}

  track(eventType: ProductEventType, routeId: string, entity?: { type: string; id: string }): void {
    if (this.#events.length >= 20) this.#events.shift()
    this.#events.push({
      eventType,
      routeId: canonicalProductRoute(routeId),
      ...(entity ? { entityType: entity.type, entityId: entity.id } : {}),
      ...environment(),
    })
    void this.flush()
  }

  async flush(): Promise<void> {
    if (this.#flushing || this.#events.length === 0) return
    this.#flushing = true
    const events = this.#events.splice(0, 20)
    try {
      await this.fetchImplementation(`${this.apiBase}/analytics/events`, {
        method: 'POST',
        credentials: 'include',
        keepalive: true,
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ events }),
      })
    } catch {
      // Best effort by design: do not retry or persist telemetry offline.
    } finally {
      this.#flushing = false
      if (this.#events.length > 0) void this.flush()
    }
  }
}

export function ProductPageView({ audience, pathname }: { audience: Audience; pathname: string }) {
  const runtime = useRuntimeConfig()
  const tracker = useMemo(
    () => new ProductAnalyticsTracker(audience, runtime.apiBase),
    [audience, runtime.apiBase],
  )
  useEffect(() => {
    tracker.track('page.view', pathname)
  }, [pathname, tracker])
  useEffect(() => {
    const onAction = (event: Event) => {
      const detail = (event as CustomEvent<{ eventType: Exclude<ProductEventType, 'page.view'>; entity?: { type: string; id: string } }>).detail
      if (detail) tracker.track(detail.eventType, window.location.pathname, detail.entity)
    }
    window.addEventListener(PRODUCT_ACTION_EVENT, onAction)
    return () => window.removeEventListener(PRODUCT_ACTION_EVENT, onAction)
  }, [tracker])
  useEffect(() => {
    const flush = () => void tracker.flush()
    window.addEventListener('pagehide', flush)
    return () => window.removeEventListener('pagehide', flush)
  }, [tracker])
  return null
}
