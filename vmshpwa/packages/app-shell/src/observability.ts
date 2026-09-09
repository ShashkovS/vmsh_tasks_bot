import * as Sentry from '@sentry/react'
import type { Breadcrumb, Event } from '@sentry/react'
import { ApiResponseError } from '@vmsh/contracts'

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
  if (event.user?.id) sanitized.user = { id: event.user.id }
  else delete sanitized.user
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

export function setObservabilityUser(accountId: string | null) {
  Sentry.setUser(accountId ? { id: accountId } : null)
}

const reportedErrors = new WeakSet<object>()

/** Allowlisted diagnostics only; see docs/submission-error-diagnostics.md. */
export function reportHandledError(
  error: unknown,
  operation: string,
  context: {
    accountId?: string
    problemId?: string
    outboxId?: string
    attempts?: number
  } = {},
) {
  if (error !== null && typeof error === 'object') {
    if (reportedErrors.has(error)) return
    reportedErrors.add(error)
  }
  const api = error instanceof ApiResponseError ? error : null
  // Do not forward original messages, causes, details or mutation variables: these can contain answers.
  try {
    Sentry.captureException(
      new Error(
        `PWA ${operation}: ${api ? 'API failure' : error instanceof Error ? error.name : 'Unknown failure'}`,
      ),
      {
        ...(context.accountId ? { user: { id: context.accountId } } : {}),
        tags: {
          operation,
          ...(api ? { http_status: String(api.status), api_code: api.code } : {}),
        },
        extra: {
          ...context,
          requestId: api?.requestId,
          online: typeof navigator === 'undefined' ? null : navigator.onLine,
        },
      },
    )
  } catch {
    // Diagnostics must not change delivery or prevent an error from being shown.
  }
}

export function submissionFailureMessage(error?: unknown, storedLabel?: string): string {
  const api = error instanceof ApiResponseError ? error : null
  const status = api?.status ?? Number(storedLabel?.split(':')[1])
  let message: string
  if (status === 401) message = 'Сессия истекла. Войдите снова, затем повторите отправку.'
  else if (status === 403)
    message = 'Сервер запретил отправку. Проверьте доступ к задаче или обратитесь к преподавателю.'
  else if (status === 429)
    message = 'Слишком много запросов. Подождите немного и повторите отправку.'
  else if (status >= 500)
    message = 'Ошибка сервера. Это не проблема вашего интернета. Повторите отправку позже.'
  else if (api) message = api.message
  else if (status >= 400)
    message = 'Сервер отклонил отправку. Обновите задачу и проверьте условия приёма.'
  else if (
    (error instanceof Error && /NetworkError|AbortError/.test(error.name)) ||
    /NetworkError|AbortError/.test(storedLabel ?? '')
  )
    message =
      'Не удалось дождаться ответа сервера. Причиной может быть связь или недоступность сервера. Повторите отправку.'
  else if (error || storedLabel)
    message =
      'Ошибка приложения при отправке. Повторите попытку; если ошибка остаётся, сообщите преподавателю.'
  else message = 'Отправка ещё не подтверждена. Нажмите «Повторить».'
  const code = api ? `HTTP ${api.status}, ${api.code}; запрос ${api.requestId}` : storedLabel
  return `${message}${code ? ` Код: ${code}.` : ''}`
}
