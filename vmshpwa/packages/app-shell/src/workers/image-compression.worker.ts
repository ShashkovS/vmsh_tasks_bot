import {
  calculateImageCompressionSize,
  WRITTEN_IMAGE_MAX_DIMENSION,
  type ImageCompressionRequest,
  type ImageCompressionResponse,
} from '../image-compression'

function respond(response: ImageCompressionResponse): void {
  self.postMessage(response)
}

self.onmessage = async (
  event: MessageEvent<ImageCompressionRequest | { requestId: string; probe: true }>,
) => {
  const { requestId } = event.data
  if ('probe' in event.data) {
    try {
      const canvas = new OffscreenCanvas(1, 1)
      canvas.getContext('2d')?.fillRect(0, 0, 1, 1)
      const blob = await canvas.convertToBlob({ type: 'image/webp', quality: 0.82 })
      self.postMessage({ requestId, supported: blob.type === 'image/webp' && blob.size > 0 })
    } catch {
      self.postMessage({ requestId, supported: false })
    }
    return
  }
  let bitmap: ImageBitmap
  try {
    bitmap = await createImageBitmap(event.data.file, { imageOrientation: 'from-image' })
  } catch {
    respond({
      requestId,
      status: 'server-fallback',
      reason: 'decode-failed',
    })
    return
  }

  try {
    const { width, height } = calculateImageCompressionSize(
      bitmap.width,
      bitmap.height,
      WRITTEN_IMAGE_MAX_DIMENSION,
    )
    const canvas = new OffscreenCanvas(width, height)
    const context = canvas.getContext('2d')
    if (!context) {
      respond({ requestId, status: 'server-fallback', reason: 'processing-failed' })
      return
    }
    context.drawImage(bitmap, 0, 0, width, height)
    let blob: Blob
    try {
      blob = await canvas.convertToBlob({
        type: 'image/webp',
        quality: event.data.quality,
      })
    } catch {
      respond({
        requestId,
        status: 'server-fallback',
        reason: 'webp-unavailable',
      })
      return
    }
    if (blob.type !== 'image/webp' || blob.size === 0 || blob.size > 20 * 1024 * 1024) {
      respond({ requestId, status: 'server-fallback', reason: 'webp-unavailable' })
      return
    }
    respond({ requestId, status: 'ready', blob, width, height })
  } catch {
    respond({ requestId, status: 'server-fallback', reason: 'processing-failed' })
  } finally {
    bitmap.close()
  }
}

export {}
