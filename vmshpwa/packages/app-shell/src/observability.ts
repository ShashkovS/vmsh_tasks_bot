import * as Sentry from '@sentry/react'
import type { Breadcrumb, Event } from '@sentry/react'

export interface FrontendObservabilityOptions {
  audience: 'student' | 'family' | 'staff'
  dsn: string | undefined
  enabled: boolean
  environment: string
  release: string | undefined
}

let initialized = false

const REDACTED = '[redacted]'
const sensitiveKey =
  /(answer|attachment|authorization|body|comment|cookie|credential|password|photo|refresh|solution|telegram|text|token)/i

function safeString(value: string): string {
  if (/\/sol_imgs\//i.test(value)) return '[redacted-media-url]'
  if (/^https?:\/\//i.test(value)) return value.split(/[?#]/, 1)[0] ?? value
  return value
}

function safeValue(value: unknown, key = ''): unknown {
  if (sensitiveKey.test(key)) return REDACTED
  if (typeof value === 'string') return safeString(value)
  if (Array.isArray(value)) return value.map((item) => safeValue(item))
  if (value !== null && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value).map(([nestedKey, nestedValue]) => [
        nestedKey,
        safeValue(nestedValue, nestedKey),
      ]),
    )
  }
  return value
}

export function sanitizeSentryBreadcrumb(breadcrumb: Breadcrumb): Breadcrumb {
  const hidesInteractionText = /^(console|ui\.)/.test(breadcrumb.category ?? '')
  const sanitized = { ...breadcrumb }
  if (breadcrumb.message) {
    sanitized.message = hidesInteractionText ? REDACTED : safeString(breadcrumb.message)
  }
  if (breadcrumb.data) {
    sanitized.data = safeValue(breadcrumb.data) as NonNullable<Breadcrumb['data']>
  }
  return sanitized
}

export function sanitizeSentryEvent<T extends Event>(event: T): T {
  const sanitized = { ...event }
  delete sanitized.user
  const request = event.request ? { ...event.request } : undefined
  if (request) {
    delete request.cookies
    delete request.data
    delete request.headers
    delete request.env
    if (request.url) request.url = safeString(request.url)
    sanitized.request = request
  }
  if (event.extra) {
    sanitized.extra = safeValue(event.extra) as NonNullable<Event['extra']>
  }
  if (event.contexts) {
    sanitized.contexts = safeValue(event.contexts) as NonNullable<Event['contexts']>
  }
  if (event.breadcrumbs) {
    sanitized.breadcrumbs = event.breadcrumbs.map(sanitizeSentryBreadcrumb)
  }
  return sanitized
}

export function initFrontendObservability(options: FrontendObservabilityOptions) {
  if (initialized || !options.enabled || !options.dsn) return

  Sentry.init({
    dsn: options.dsn,
    enabled: true,
    environment: options.environment,
    ...(options.release ? { release: options.release } : {}),
    sendDefaultPii: false,
    attachStacktrace: true,
    beforeSend: sanitizeSentryEvent,
    beforeBreadcrumb: sanitizeSentryBreadcrumb,
    initialScope: {
      tags: { audience: options.audience },
    },
  })
  initialized = true
}
