export interface ImageCompressionRequest {
  file: File
  maxDimension: number
  quality: number
}

self.onmessage = async (event: MessageEvent<ImageCompressionRequest>) => {
  const bitmap = await createImageBitmap(event.data.file)
  const scale = Math.min(1, event.data.maxDimension / Math.max(bitmap.width, bitmap.height))
  const width = Math.max(1, Math.round(bitmap.width * scale))
  const height = Math.max(1, Math.round(bitmap.height * scale))
  const canvas = new OffscreenCanvas(width, height)
  const context = canvas.getContext('2d')
  if (!context) throw new Error('Canvas 2D context is unavailable')
  context.drawImage(bitmap, 0, 0, width, height)
  bitmap.close()
  const blob = await canvas.convertToBlob({ type: 'image/webp', quality: event.data.quality })
  self.postMessage({ blob, width, height })
}

export {}
