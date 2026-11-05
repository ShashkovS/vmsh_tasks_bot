import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  WRITTEN_IMAGE_DEFAULT_QUALITY,
  WRITTEN_IMAGE_MAX_DIMENSION,
  WRITTEN_IMAGE_MAX_SOURCE_BYTES,
  calculateImageCompressionSize,
  compressWrittenSubmissionImage,
  type ImageCompressionRequest,
  type ImageCompressionWorkerLike,
} from './image-compression'

const REQUEST_ID = '00000000-0000-4000-8000-000000000001'

class FakeWorker implements ImageCompressionWorkerLike {
  readonly messages: ImageCompressionRequest[] = []
  terminated = false
  readonly #messageListeners: Array<(event: MessageEvent<unknown>) => void> = []
  readonly #errorListeners: Array<(event: ErrorEvent) => void> = []

  addEventListener(
    type: 'message' | 'error',
    listener: ((event: MessageEvent<unknown>) => void) | ((event: ErrorEvent) => void),
  ) {
    if (type === 'message') {
      this.#messageListeners.push(listener as (event: MessageEvent<unknown>) => void)
    } else {
      this.#errorListeners.push(listener as (event: ErrorEvent) => void)
    }
  }

  postMessage(message: ImageCompressionRequest) {
    this.messages.push(message)
  }

  terminate() {
    this.terminated = true
  }

  emitMessage(data: unknown) {
    for (const listener of this.#messageListeners) {
      listener(new MessageEvent('message', { data }))
    }
  }

  emitError() {
    for (const listener of this.#errorListeners) listener(new ErrorEvent('error'))
  }
}

function source(name = 'solution.jpg', mediaType = 'image/jpeg'): File {
  return new File(['original-image'], name, { type: mediaType })
}

function options(worker: FakeWorker) {
  return {
    workerFactory: () => worker,
    randomUUID: () => REQUEST_ID,
  }
}

afterEach(() => {
  vi.useRealTimers()
})

describe('written image compression boundary', () => {
  it('keeps small dimensions and scales a long side to 1920 without distortion', () => {
    expect(calculateImageCompressionSize(800, 600)).toEqual({ width: 800, height: 600 })
    expect(calculateImageCompressionSize(4032, 3024)).toEqual({ width: 1920, height: 1440 })
    expect(calculateImageCompressionSize(1, 10_000)).toEqual({ width: 1, height: 1920 })
    expect(() => calculateImageCompressionSize(0, 100)).toThrow('positive')
  })

  it('returns only a validated WebP and terminates its one-shot worker', async () => {
    const worker = new FakeWorker()
    const file = source('my.solution.jpeg')
    const compressed = {
      size: 11,
      type: 'image/webp',
      arrayBuffer: () => Promise.resolve(new ArrayBuffer(11)),
    } as Blob
    const pending = compressWrittenSubmissionImage(file, options(worker))

    expect(worker.messages).toEqual([
      { requestId: REQUEST_ID, file, quality: WRITTEN_IMAGE_DEFAULT_QUALITY },
    ])
    worker.emitMessage({
      requestId: '00000000-0000-4000-8000-000000000099',
      status: 'ready',
      blob: compressed,
      width: 100,
      height: 100,
    })
    expect(worker.terminated).toBe(false)
    worker.emitMessage({
      requestId: REQUEST_ID,
      status: 'ready',
      blob: compressed,
      width: WRITTEN_IMAGE_MAX_DIMENSION,
      height: 1440,
    })

    await expect(pending).resolves.toEqual({
      status: 'ready',
      blob: compressed,
      fileName: 'my.solution.webp',
      width: 1920,
      height: 1440,
    })
    expect(worker.terminated).toBe(true)
  })

  it('keeps the exact source for an explicit HEIC/server conversion fallback', async () => {
    const worker = new FakeWorker()
    const file = source('iphone.heic', '')
    const pending = compressWrittenSubmissionImage(file, options(worker))
    worker.emitMessage({
      requestId: REQUEST_ID,
      status: 'server-fallback',
      reason: 'decode-failed',
    })

    await expect(pending).resolves.toEqual({
      status: 'server-fallback',
      source: file,
      reason: 'decode-failed',
    })
    expect(worker.terminated).toBe(true)
  })

  it('falls back safely for unavailable, failed and malformed workers', async () => {
    const file = source()
    await expect(
      compressWrittenSubmissionImage(file, {
        workerFactory: () => {
          throw new Error('Worker construction failed')
        },
      }),
    ).resolves.toMatchObject({ status: 'server-fallback', reason: 'worker-unavailable' })

    const failed = new FakeWorker()
    const failedResult = compressWrittenSubmissionImage(file, options(failed))
    failed.emitError()
    await expect(failedResult).resolves.toMatchObject({
      status: 'server-fallback',
      reason: 'processing-failed',
    })

    const malformed = new FakeWorker()
    const malformedResult = compressWrittenSubmissionImage(file, options(malformed))
    malformed.emitMessage({ requestId: REQUEST_ID, status: 'ready', blob: 'not-a-blob' })
    await expect(malformedResult).resolves.toMatchObject({
      status: 'server-fallback',
      reason: 'worker-invalid-response',
    })
  })

  it('bounds a worker that never answers', async () => {
    vi.useFakeTimers()
    const worker = new FakeWorker()
    const pending = compressWrittenSubmissionImage(source(), {
      ...options(worker),
      timeoutMilliseconds: 500,
    })

    await vi.advanceTimersByTimeAsync(500)

    await expect(pending).resolves.toMatchObject({
      status: 'server-fallback',
      reason: 'worker-timeout',
    })
    expect(worker.terminated).toBe(true)
  })

  it('aborts without retaining a hidden worker', async () => {
    const worker = new FakeWorker()
    const controller = new AbortController()
    const pending = compressWrittenSubmissionImage(source(), {
      ...options(worker),
      signal: controller.signal,
    })
    controller.abort()

    await expect(pending).rejects.toMatchObject({ name: 'AbortError' })
    expect(worker.terminated).toBe(true)
  })

  it('rejects invalid source and tuning values before a worker is created', async () => {
    const workerFactory = vi.fn(() => new FakeWorker())
    await expect(
      compressWrittenSubmissionImage(source('notes.txt', 'text/plain'), { workerFactory }),
    ).rejects.toThrow('supported image')
    await expect(
      compressWrittenSubmissionImage(
        {
          name: 'large.jpg',
          type: 'image/jpeg',
          size: WRITTEN_IMAGE_MAX_SOURCE_BYTES + 1,
        } as File,
        { workerFactory },
      ),
    ).rejects.toThrow('25 MiB')
    await expect(
      compressWrittenSubmissionImage(source(), { workerFactory, quality: 0 }),
    ).rejects.toThrow('quality')
    expect(workerFactory).not.toHaveBeenCalled()
  })
})
