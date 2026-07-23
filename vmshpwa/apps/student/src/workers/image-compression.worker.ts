export interface ImageCompressionRequest {
  file: File
  quality?: number
}

export type ImageCompressionResponse =
  | { status: 'ready'; blob: Blob; width: number; height: number }
  | { status: 'server-fallback'; reason: 'decode-failed' | 'webp-unavailable' }

const MAX_DIMENSION = 1920
const DEFAULT_QUALITY = 0.82

self.onmessage = async (event: MessageEvent<ImageCompressionRequest>) => {
  let bitmap: ImageBitmap
  try {
    bitmap = await createImageBitmap(event.data.file, { imageOrientation: 'from-image' })
  } catch {
    self.postMessage({
      status: 'server-fallback',
      reason: 'decode-failed',
    } satisfies ImageCompressionResponse)
    return
  }

  try {
    const scale = Math.min(1, MAX_DIMENSION / Math.max(bitmap.width, bitmap.height))
    const width = Math.max(1, Math.round(bitmap.width * scale))
    const height = Math.max(1, Math.round(bitmap.height * scale))
    const canvas = new OffscreenCanvas(width, height)
    const context = canvas.getContext('2d')
    if (!context) throw new Error('Canvas 2D context is unavailable')
    context.drawImage(bitmap, 0, 0, width, height)
    const blob = await canvas.convertToBlob({
      type: 'image/webp',
      quality: event.data.quality ?? DEFAULT_QUALITY,
    })
    if (blob.type !== 'image/webp') {
      self.postMessage({
        status: 'server-fallback',
        reason: 'webp-unavailable',
      } satisfies ImageCompressionResponse)
      return
    }
    self.postMessage({ status: 'ready', blob, width, height } satisfies ImageCompressionResponse)
  } finally {
    bitmap.close()
  }
}

export {}
