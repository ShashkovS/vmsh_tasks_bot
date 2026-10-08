import { ApiResponseError, ServiceTransportError } from '@vmsh/contracts'

/** Bounded classification without messages/URLs; docs/performance/2026-10-08-fixes.md. */
export function queryFailure(error: unknown) {
  let cause = error
  for (
    let depth = 0;
    depth < 5 && (cause instanceof Error || cause instanceof DOMException);
    depth++
  ) {
    if (cause instanceof ServiceTransportError)
      return { kind: cause.kind, expected: cause.kind === 'offline' || cause.kind === 'recovering' }
    if (cause instanceof ApiResponseError) return { kind: 'api', expected: false, api: cause }
    // An IndexedDB abort or an untyped timeout is not proof of caller cancellation.
    if (cause.name === 'AbortError') return { kind: 'aborted', expected: false }
    cause = cause instanceof Error ? cause.cause : undefined
  }
  return { kind: 'unknown', expected: false }
}

export function retryQuery(failureCount: number, error: unknown): boolean {
  const failure = queryFailure(error)
  return (
    failureCount < 1 &&
    !failure.expected &&
    failure.kind !== 'aborted' &&
    !(failure.api && failure.api.status >= 400 && failure.api.status < 500)
  )
}

const families = new Set([
  'auth',
  'runtime',
  'courses',
  'content',
  'notifications',
  'sessions',
  'test-input',
  'test-attempts',
  'written-submissions',
  'oral',
  'news',
  'support',
  'statistics',
])

export function queryFamily(queryKey: readonly unknown[]): string {
  const family = queryKey[0] === 'principal' ? queryKey[3] : queryKey[0]
  return typeof family === 'string' && families.has(family) ? family : 'other'
}
