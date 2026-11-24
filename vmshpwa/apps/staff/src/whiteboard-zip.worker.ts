import { zipSync } from 'fflate'
self.onmessage = (event: MessageEvent<Record<string, Uint8Array>>) => {
  const bytes = zipSync(event.data, { level: 0 })
  self.postMessage(bytes, { transfer: [bytes.buffer] })
}
