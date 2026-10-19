import { t } from '@lingui/core/macro'
import * as Sentry from '@sentry/react'
import type { Breadcrumb, Event } from '@sentry/react'
import {
  ApiResponseError,
  setServiceEpisodeReporter,
  serviceAvailabilitySnapshot,
} from '@vmsh/contracts'
import { queryFailure, queryFamily } from './query-errors'
import { createSentryEventFilter, expectedHandledFailure } from './sentry-noise'
import { createSentryAdmission } from './sentry-admission'

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

  const filterEvent = createSentryEventFilter()
  const admitEvent = createSentryAdmission(options.audience)
  Sentry.init({
    dsn: options.dsn,
    enabled: true,
    environment: options.environment,
    ...(options.release ? { release: options.release } : {}),
    sendDefaultPii: false,
    sendClientReports: false,
    tracesSampleRate: 0,
    enableLogs: false,
    attachStacktrace: true,
    // SDK Dedupe has no time window and runs before sampling; our filter owns repeats.
    // GlitchTip receives errors only; migration-20261011.md excludes session telemetry.
    integrations: (defaults) =>
      defaults.filter((integration) => !['Dedupe', 'BrowserSession'].includes(integration.name)),
    beforeSend: async (event) => {
      const filtered = filterEvent(event)
      if (!filtered) return null
      const sanitized = sanitizeSentryEvent(filtered)
      return (await admitEvent(sanitized)) ? sanitized : null
    },
    beforeBreadcrumb: sanitizeSentryBreadcrumb,
    initialScope: {
      tags: { audience: options.audience },
    },
  })
  initialized = true
  setServiceEpisodeReporter((event) => {
    Sentry.addBreadcrumb({ category: 'service.recovery', level: 'info', data: event })
    // Recovery is diagnostic context, not an event; 2026-10-11 Sentry quota decision.
  })
}

export function setObservabilityUser(accountId: string | null) {
  Sentry.setUser(accountId ? { id: accountId } : null)
}

const reportedErrors = new WeakSet<object>()
const breadcrumbErrors = new WeakSet<object>()

/** Public build locations only; docs/performance/2026-10-10-sentry-noise.md. */
function handledDiagnosticError(
  error: unknown,
  message: string,
): { error: Error; location?: string } {
  const safeError = new Error(message)
  let originalLocation: string | undefined
  // Keep the application's original failure location without its message,
  // function names, arbitrary URLs, or private data in a wrapped cause.
  try {
    let cause = error
    let frames: string[] = []
    for (let depth = 0; depth < 5 && cause instanceof Error; depth++) {
      const locations = (cause.stack ?? '')
        .split('\n')
        .slice(0, 21)
        .flatMap((line) => {
          const match = /(https?:\/\/[^\s)]+):(\d+):(\d+)\)?$/.exec(line)
          if (!match) return []
          const url = new URL(match[1]!)
          if (
            typeof location === 'undefined' ||
            url.origin !== location.origin ||
            !/^\/(student|family|staff)\/assets\/[\w.-]+\.js$/.test(url.pathname)
          )
            return []
          return [`    at ${url.origin}${url.pathname}:${match[2]}:${match[3]}`]
        })
      if (locations.length) frames = locations
      cause = cause.cause
    }
    if (frames.length) {
      safeError.stack = `Error: ${message}\n${frames.join('\n')}`
      originalLocation = frames[0]?.replace(/^ {4}at https?:\/\/[^/]+/, '')
    }
  } catch {
    // A malformed stack must not prevent the safe synthetic diagnostic.
  }
  return { error: safeError, ...(originalLocation ? { location: originalLocation } : {}) }
}

/** Allowlisted diagnostics only; see docs/submission-error-diagnostics.md. */
export function reportHandledError(
  error: unknown,
  operation: string,
  context: {
    accountId?: string
    problemId?: string
    outboxId?: string
    attempts?: number
    queryFamily?: string
  } = {},
) {
  const failure = queryFailure(error)
  const family = queryFamily([context.queryFamily])
  if (expectedHandledFailure(failure, operation, family)) return
  if (error !== null && typeof error === 'object' && reportedErrors.has(error)) return
  const api = failure.api ?? null
  const errorType = api ? 'API failure' : error instanceof Error ? error.name : 'Unknown failure'
  // Do not forward original messages, causes, details or mutation variables: these can contain answers.
  try {
    const diagnostic = handledDiagnosticError(error, `PWA ${operation}: ${errorType}`)
    if (
      operation === 'query' &&
      (['network', 'deadline'].includes(failure.kind) ||
        (failure.kind === 'unknown' && errorType === 'TypeError' && !diagnostic.location))
    ) {
      if (error !== null && typeof error === 'object') {
        if (breadcrumbErrors.has(error)) return
        breadcrumbErrors.add(error)
      }
      Sentry.addBreadcrumb({
        category: 'query.failure',
        level: 'info',
        message: diagnostic.error.message,
        data: { queryFamily: family, transportKind: failure.kind },
      })
      return
    }
    if (error !== null && typeof error === 'object') reportedErrors.add(error)
    Sentry.captureException(diagnostic.error, {
      ...(context.accountId ? { user: { id: context.accountId } } : {}),
      // Semantic groups survive minification; see docs/performance/2026-10-10-sentry-noise.md.
      fingerprint: [
        'pwa-handled-v1',
        operation,
        operation === 'query' ? family : 'write',
        failure.kind,
        errorType,
        ...(api ? [String(api.status), api.code] : []),
        ...(failure.kind === 'unknown' && diagnostic.location ? [diagnostic.location] : []),
      ],
      tags: {
        operation,
        diagnostic_source: diagnostic.location ? 'original' : 'synthetic',
        ...(operation === 'query' ? { query_family: family, transport_kind: failure.kind } : {}),
        ...(api ? { http_status: String(api.status), api_code: api.code } : {}),
      },
      extra: {
        ...context,
        ...(context.queryFamily ? { queryFamily: family } : {}),
        requestId: api?.requestId,
        online: typeof navigator === 'undefined' ? null : navigator.onLine,
      },
    })
  } catch {
    // Diagnostics must not change delivery or prevent an error from being shown.
  }
}

function submissionFailureDomainCode(error?: unknown, storedLabel?: string): string | undefined {
  const api = error instanceof ApiResponseError ? error : null
  return api?.code ?? storedLabel?.split(':')[2]
}

export function submissionDeadlineMessage(): string {
  return t`Срок сдачи закончился, поэтому ответ не отправлен. Черновик сохранён на этом устройстве.`
}

export function isSubmissionDeadlineFailure(error?: unknown, storedLabel?: string): boolean {
  return submissionFailureDomainCode(error, storedLabel) === 'submission_deadline_passed'
}

export function submissionFailureMessage(error?: unknown, storedLabel?: string): string {
  const api = error instanceof ApiResponseError ? error : null
  const domainCode = submissionFailureDomainCode(error, storedLabel)
  if (domainCode === 'request_not_confirmed')
    return t`Сервер не подтвердил отправку. Ответ сохранён; проверьте результат перед повтором.`
  if (domainCode === 'service_updating' || serviceAvailabilitySnapshot().state === 'updating')
    return t`Обновляем сервис. Отправим после обновления.`
  if (domainCode === 'submission_deadline_passed') return submissionDeadlineMessage()
  if (domainCode === 'test_attempt_hour_limit')
    return t`На эту задачу закончились попытки на текущий час. Вернитесь к ней позже. Ответ не отправлен; автоматически отправлять его не будем.`
  if (domainCode === 'test_attempt_day_limit')
    return t`На эту задачу закончились попытки на сегодня. Вернитесь к ней завтра. Ответ не отправлен; автоматически отправлять его не будем.`
  if (storedLabel === 'client:stale-sending-lease')
    return t`Предыдущая отправка прервалась до подтверждения. Ответ сохранён — нажмите «Повторить».`
  const status = api?.status ?? Number(storedLabel?.split(':')[1])
  let message: string
  if (status === 401) message = t`Сессия истекла. Войдите снова, затем повторите отправку.`
  else if (status === 403)
    message = t`Сервер запретил отправку. Проверьте доступ к задаче или обратитесь к преподавателю.`
  else if (status === 429)
    message = t`Слишком много запросов. Подождите немного и повторите отправку.`
  else if (status >= 500)
    message = t`Ошибка сервера. Это не проблема вашего интернета. Повторите отправку позже.`
  else if (api) message = api.message
  else if (status >= 400)
    message = t`Сервер отклонил отправку. Обновите задачу и проверьте условия приёма.`
  else if (
    (error instanceof Error && /TimeoutError/.test(error.name)) ||
    /TimeoutError/.test(storedLabel ?? '')
  )
    message = t`Сервер не ответил за 30 секунд. Ответ сохранён — повторите отправку. Это не означает, что на устройстве нет интернета.`
  else if (
    (error instanceof Error && /NetworkError|AbortError/.test(error.name)) ||
    /NetworkError|AbortError/.test(storedLabel ?? '')
  )
    message = t`Не удалось дождаться ответа сервера. Причиной может быть связь или недоступность сервера. Повторите отправку.`
  else if (error || storedLabel)
    message = t`Ошибка приложения при отправке. Повторите попытку; если ошибка остаётся, сообщите преподавателю.`
  else message = t`Отправка ещё не подтверждена. Нажмите «Повторить».`
  const code = api ? t`HTTP ${api.status}, ${api.code}; запрос ${api.requestId}` : storedLabel
  return `${message}${code ? t` Код: ${code}.` : ''}`
}
