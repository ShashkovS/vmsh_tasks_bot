export const DEFAULT_SUBMISSION_REQUEST_TIMEOUT_MS = 30_000

export class RequestDeadlineExceededError extends Error {
  readonly timeoutMilliseconds: number

  constructor(timeoutMilliseconds: number) {
    super(`Request did not settle within ${timeoutMilliseconds}ms`)
    this.name = 'RequestDeadlineExceededError'
    this.timeoutMilliseconds = timeoutMilliseconds
  }
}

interface RequestDeadlineOptions {
  signal?: AbortSignal
  timeoutMilliseconds: number
}

function cancellationReason(signal: AbortSignal): Error {
  return signal.reason instanceof Error
    ? signal.reason
    : new DOMException('The request was cancelled', 'AbortError')
}

/**
 * Bound a browser request even when the network stack leaves fetch pending.
 * See `docs/submission-error-diagnostics.md`, request-deadline recovery.
 */
export async function withRequestDeadline<T>(
  operation: (signal: AbortSignal) => Promise<T>,
  { signal: callerSignal, timeoutMilliseconds }: RequestDeadlineOptions,
): Promise<T> {
  if (!Number.isSafeInteger(timeoutMilliseconds) || timeoutMilliseconds < 1) {
    throw new RangeError('Request timeout must be a positive integer')
  }

  const controller = new AbortController()
  const abortFromCaller = () => {
    controller.abort(
      callerSignal
        ? cancellationReason(callerSignal)
        : new DOMException('The request was cancelled', 'AbortError'),
    )
  }
  if (callerSignal?.aborted) abortFromCaller()
  else callerSignal?.addEventListener('abort', abortFromCaller, { once: true })

  const deadlineError = new RequestDeadlineExceededError(timeoutMilliseconds)
  const timeout = setTimeout(() => controller.abort(deadlineError), timeoutMilliseconds)
  const aborted = new Promise<never>((_resolve, reject) => {
    if (controller.signal.aborted) {
      reject(cancellationReason(controller.signal))
      return
    }
    controller.signal.addEventListener(
      'abort',
      () => reject(cancellationReason(controller.signal)),
      { once: true },
    )
  })

  try {
    return await Promise.race([operation(controller.signal), aborted])
  } finally {
    clearTimeout(timeout)
    callerSignal?.removeEventListener('abort', abortFromCaller)
  }
}
