import {
  ApiResponseError,
  apiErrorSchema,
  pwaFetch,
  preparedImageSchema,
  imageUploadGrantSchema,
  type PreparedImage,
  type ImageUploadGrant,
  type ImageUploadPurpose,
  type RuntimeConfig,
} from '@vmsh/contracts'
import { compressWrittenSubmissionImage, initializeImageCompression } from './image-compression'

// URLs belong only to the client instance; durable drafts retain metadata/bytes.
// See docs/performance/browser-image-uploads.md and the existing outbox leases.
const descriptions = new WeakMap<Blob, PreparedImage>()
export function preparedImageMetadata(blob: Blob): PreparedImage | undefined {
  return descriptions.get(blob)
}
export function recordImageTiming(name: string, started: number): void {
  const clock = globalThis.performance
  if (typeof clock?.measure === 'function')
    clock.measure(`vmsh.image.${name}`, { start: started, end: clock.now() })
}

export async function describePreparedImage(
  blob: Blob,
  input: Omit<PreparedImage, 'sha256' | 'byteSize'>,
): Promise<PreparedImage> {
  const hash = await crypto.subtle.digest('SHA-256', await blob.arrayBuffer())
  const sha256 = [...new Uint8Array(hash)]
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('')
  return preparedImageSchema.parse({ ...input, sha256, byteSize: blob.size })
}

export class ImageUploadClient {
  readonly #fetch: typeof fetch
  readonly #grants = new Map<string, Promise<ImageUploadGrant>>()
  constructor(
    readonly runtime: RuntimeConfig,
    readonly purpose: ImageUploadPurpose,
    readonly context: Record<string, string>,
    readonly options: {
      fetchImplementation?: typeof fetch
      refreshSession?: () => Promise<unknown>
    } = {},
  ) {
    this.#fetch = options.fetchImplementation ?? pwaFetch
    this.initialize()
  }

  initialize(): void {
    void initializeImageCompression()
  }

  async preparePhoto(file: File, signal?: AbortSignal): Promise<Blob> {
    const started = performance.now()
    const result = await compressWrittenSubmissionImage(file, { ...(signal ? { signal } : {}) })
    recordImageTiming('prepare', started)
    if (result.status !== 'ready') return result.source
    const metadata = await describePreparedImage(result.blob, {
      clientId: crypto.randomUUID(),
      filename: result.fileName,
      width: result.width,
      height: result.height,
    })
    descriptions.set(result.blob, metadata)
    this.prefetch(metadata)
    return result.blob
  }

  prefetch(metadata: PreparedImage): void {
    void this.#grant(metadata).catch(() => {
      /* Local draft remains usable offline. */
    })
  }

  async #json(path: string, body: unknown): Promise<unknown> {
    const send = () =>
      this.#fetch(`${this.runtime.apiBase}${path}`, {
        method: 'POST',
        credentials: 'include',
        cache: 'no-store',
        redirect: 'error',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(30_000),
      })
    let response = await send()
    if (response.status === 401 && this.options.refreshSession) {
      await response.body?.cancel()
      await this.options.refreshSession()
      response = await send()
    }
    if (response.status === 404 && path.startsWith('/image-uploads/')) {
      await response.body?.cancel()
      throw new ApiResponseError(404, {
        error: {
          code: 'image_upload_unavailable',
          message: 'Image upload protocol unavailable',
          requestId: 'image-upload-protocol',
        },
      })
    }
    const payload: unknown = await response.json()
    if (!response.ok) throw new ApiResponseError(response.status, apiErrorSchema.parse(payload))
    return payload
  }

  async #grant(metadata: PreparedImage, renew = false): Promise<ImageUploadGrant> {
    const previous = this.#grants.get(metadata.clientId)
    if (previous && !renew) {
      const grant = await previous
      if (grant.transport === 'completed' || Date.parse(grant.expiresAt) > Date.now() + 5000)
        return grant
      renew = true
    }
    const pending = (async () => {
      const old = renew && previous ? await previous : null
      return imageUploadGrantSchema.parse(
        await this.#json(
          old ? `/image-uploads/${old.uploadId}/renew` : '/image-uploads/prepare',
          old
            ? {}
            : {
                schemaVersion: 1,
                ...preparedImageSchema.parse(metadata),
                purpose: this.purpose,
                context: this.context,
              },
        ),
      )
    })()
    this.#grants.set(metadata.clientId, pending)
    try {
      return await pending
    } catch (error) {
      if (this.#grants.get(metadata.clientId) === pending) this.#grants.delete(metadata.clientId)
      throw error
    }
  }

  async upload<T>(
    blob: Blob,
    metadata: PreparedImage,
    endpoint: string,
    parser: (payload: unknown) => T,
    proxy: (headers: Record<string, string>) => Promise<T>,
    binding: Record<string, unknown> = {},
  ): Promise<T> {
    const started = performance.now()
    let grant: ImageUploadGrant
    try {
      grant = await this.#grant(metadata)
    } catch (error) {
      if (error instanceof ApiResponseError && error.status === 410) {
        // Tombstones cannot be revived while a cleanup delete might still run.
        grant = await this.#grant(metadata)
      } else if (error instanceof ApiResponseError && [404, 503].includes(error.status)) {
        return proxy({ 'X-Vmsh-Prepared-WebP': '1' })
      } else throw error
    }
    const finalize = () =>
      this.#json(endpoint, { schemaVersion: 1, ...binding, uploadId: grant.uploadId }).then(parser)
    const proxied = () =>
      proxy({ 'X-Vmsh-Prepared-WebP': '1', 'X-Vmsh-Image-Upload': grant.uploadId })
    try {
      if (grant.transport === 'completed') return await finalize()
      if (grant.transport === 'proxy') return await proxied()
      for (let attempt = 0; attempt < 2; attempt++) {
        if (grant.transport !== 's3') return await proxied()
        const uploading = performance.now()
        try {
          const response = await this.#fetch(grant.url, {
            method: 'PUT',
            body: blob,
            headers: grant.headers,
            credentials: 'omit',
            redirect: 'error',
            cache: 'no-store',
            signal: AbortSignal.timeout(60_000),
          })
          await response.body?.cancel()
          // Even a failed/lost PUT response may have committed: HEAD decides.
        } catch {
          /* Finalize before retrying any bytes. */
        } finally {
          recordImageTiming('put', uploading)
        }
        try {
          return await finalize()
        } catch (error) {
          if (
            !(error instanceof ApiResponseError) ||
            !['image_upload_not_uploaded', 'image_upload_unavailable'].includes(error.code)
          )
            throw error
          if (error.code === 'image_upload_unavailable') return await proxied()
          if (attempt === 0) grant = await this.#grant(metadata, true)
        }
      }
      return await proxied()
    } finally {
      recordImageTiming('send-to-upload-receipt', started)
    }
  }
}
