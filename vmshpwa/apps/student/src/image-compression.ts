/**
 * Browser boundary for Phase-5 written-photo compression. A successful worker
 * result is the only source retained; otherwise the original file is returned
 * explicitly for the bounded aiohttp conversion fallback. See
 * `dev/development-plan/09-phase-5-written-submissions.md`.
 */

export const WRITTEN_IMAGE_MAX_DIMENSION = 1920
export const WRITTEN_IMAGE_DEFAULT_QUALITY = 0.82
export const WRITTEN_IMAGE_MAX_SOURCE_BYTES = 25 * 1024 * 1024

export type ImageCompressionFallbackReason =
  | 'decode-failed'
  | 'webp-unavailable'
  | 'processing-failed'
  | 'worker-unavailable'
  | 'worker-timeout'
  | 'worker-invalid-response'

export interface ImageCompressionRequest {
  requestId: string
  file: File
  quality: number
}

export type ImageCompressionResponse =
  | {
      requestId: string
      status: 'ready'
      blob: Blob
      width: number
      height: number
    }
  | {
      requestId: string
      status: 'server-fallback'
      reason: 'decode-failed' | 'webp-unavailable' | 'processing-failed'
    }

export type WrittenImageCompressionResult =
  | {
      status: 'ready'
      blob: Blob
      fileName: string
      width: number
      height: number
    }
  | {
      status: 'server-fallback'
      source: File
      reason: ImageCompressionFallbackReason
    }

export interface ImageCompressionWorkerLike {
  addEventListener(type: 'message', listener: (event: MessageEvent<unknown>) => void): void
  addEventListener(type: 'error', listener: (event: ErrorEvent) => void): void
  postMessage(message: ImageCompressionRequest): void
  terminate(): void
}

export interface CompressWrittenImageOptions {
  quality?: number
  timeoutMilliseconds?: number
  signal?: AbortSignal
  randomUUID?: () => string
  workerFactory?: () => ImageCompressionWorkerLike
}

export function calculateImageCompressionSize(
  sourceWidth: number,
  sourceHeight: number,
  maxDimension = WRITTEN_IMAGE_MAX_DIMENSION,
): { width: number; height: number } {
  if (
    !Number.isFinite(sourceWidth) ||
    !Number.isFinite(sourceHeight) ||
    !Number.isSafeInteger(maxDimension) ||
    sourceWidth <= 0 ||
    sourceHeight <= 0 ||
    maxDimension <= 0
  ) {
    throw new RangeError('Image dimensions and maximum size must be positive')
  }
  const scale = Math.min(1, maxDimension / Math.max(sourceWidth, sourceHeight))
  return {
    width: Math.max(1, Math.round(sourceWidth * scale)),
    height: Math.max(1, Math.round(sourceHeight * scale)),
  }
}

function defaultWorkerFactory(): ImageCompressionWorkerLike {
  return new Worker(new URL('./workers/image-compression.worker.ts', import.meta.url), {
    type: 'module',
    name: 'vmsh-written-image-compression',
  })
}

function fallback(
  source: File,
  reason: ImageCompressionFallbackReason,
): WrittenImageCompressionResult {
  return { status: 'server-fallback', source, reason }
}

function outputFileName(sourceName: string): string {
  const trimmed = sourceName.trim()
  const base = trimmed.replace(/\.[^.]+$/, '') || 'page'
  return `${base}.webp`
}

function validateSource(file: File): void {
  if (file.size < 1 || file.size > WRITTEN_IMAGE_MAX_SOURCE_BYTES) {
    throw new RangeError('Written image source must be between 1 byte and 25 MiB')
  }
  const lowerName = file.name.toLocaleLowerCase('en-US')
  if (
    !file.type.startsWith('image/') &&
    !['.heic', '.heif'].some((extension) => lowerName.endsWith(extension))
  ) {
    throw new TypeError('Written image source must be a supported image file')
  }
}

function imageCompressionAbortError(): Error {
  const error = new Error('Image compression aborted')
  error.name = 'AbortError'
  return error
}

function isBlobLike(value: unknown): value is Blob {
  return (
    typeof value === 'object' &&
    value !== null &&
    typeof (value as Blob).size === 'number' &&
    typeof (value as Blob).type === 'string' &&
    typeof (value as Blob).arrayBuffer === 'function'
  )
}

function isReadyResponse(
  value: unknown,
  expectedRequestId: string,
): value is Extract<ImageCompressionResponse, { status: 'ready' }> {
  if (typeof value !== 'object' || value === null) return false
  const response = value as Partial<Extract<ImageCompressionResponse, { status: 'ready' }>>
  return (
    response.requestId === expectedRequestId &&
    response.status === 'ready' &&
    isBlobLike(response.blob) &&
    response.blob.type === 'image/webp' &&
    response.blob.size > 0 &&
    Number.isSafeInteger(response.width) &&
    Number.isSafeInteger(response.height) &&
    (response.width ?? 0) > 0 &&
    (response.height ?? 0) > 0 &&
    (response.width ?? 0) <= WRITTEN_IMAGE_MAX_DIMENSION &&
    (response.height ?? 0) <= WRITTEN_IMAGE_MAX_DIMENSION
  )
}

function isFallbackResponse(
  value: unknown,
  expectedRequestId: string,
): value is Extract<ImageCompressionResponse, { status: 'server-fallback' }> {
  if (typeof value !== 'object' || value === null) return false
  const response = value as Partial<
    Extract<ImageCompressionResponse, { status: 'server-fallback' }>
  >
  return (
    response.requestId === expectedRequestId &&
    response.status === 'server-fallback' &&
    ['decode-failed', 'webp-unavailable', 'processing-failed'].includes(response.reason ?? '')
  )
}

export async function compressWrittenSubmissionImage(
  file: File,
  options: CompressWrittenImageOptions = {},
): Promise<WrittenImageCompressionResult> {
  validateSource(file)
  const quality = options.quality ?? WRITTEN_IMAGE_DEFAULT_QUALITY
  if (!Number.isFinite(quality) || quality <= 0 || quality > 1) {
    throw new RangeError('Image compression quality must be greater than 0 and at most 1')
  }
  const timeoutMilliseconds = options.timeoutMilliseconds ?? 30_000
  if (!Number.isSafeInteger(timeoutMilliseconds) || timeoutMilliseconds < 1) {
    throw new RangeError('Image compression timeout must be a positive integer')
  }
  if (options.signal?.aborted) throw imageCompressionAbortError()

  const requestId = (options.randomUUID ?? (() => globalThis.crypto.randomUUID()))()
  let worker: ImageCompressionWorkerLike
  try {
    worker = (options.workerFactory ?? defaultWorkerFactory)()
  } catch {
    return fallback(file, 'worker-unavailable')
  }

  return new Promise<WrittenImageCompressionResult>((resolve, reject) => {
    let settled = false
    const finish = (result: WrittenImageCompressionResult) => {
      if (settled) return
      settled = true
      clearTimeout(timeout)
      options.signal?.removeEventListener('abort', onAbort)
      worker.terminate()
      resolve(result)
    }
    const fail = (error: unknown) => {
      if (settled) return
      settled = true
      clearTimeout(timeout)
      options.signal?.removeEventListener('abort', onAbort)
      worker.terminate()
      reject(
        error instanceof Error ? error : new Error('Image compression failed', { cause: error }),
      )
    }
    const onAbort = () => fail(imageCompressionAbortError())
    const timeout = setTimeout(() => finish(fallback(file, 'worker-timeout')), timeoutMilliseconds)

    options.signal?.addEventListener('abort', onAbort, { once: true })
    worker.addEventListener('error', () => finish(fallback(file, 'processing-failed')))
    worker.addEventListener('message', (event) => {
      const response = event.data
      if (
        typeof response === 'object' &&
        response !== null &&
        'requestId' in response &&
        response.requestId !== requestId
      ) {
        return
      }
      if (isReadyResponse(response, requestId)) {
        finish({
          status: 'ready',
          blob: response.blob,
          fileName: outputFileName(file.name),
          width: response.width,
          height: response.height,
        })
        return
      }
      if (isFallbackResponse(response, requestId)) {
        finish(fallback(file, response.reason))
        return
      }
      finish(fallback(file, 'worker-invalid-response'))
    })

    try {
      worker.postMessage({ requestId, file, quality })
    } catch {
      finish(fallback(file, 'worker-unavailable'))
    }
  })
}
