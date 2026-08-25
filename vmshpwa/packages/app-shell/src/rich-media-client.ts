import {
  ApiResponseError,
  apiErrorSchema,
  parseRuntimeConfigForAudience,
  staffRichMediaUploadResponseSchema,
  type RuntimeConfig,
  type StaffRichMediaImage,
} from '@vmsh/contracts'

export interface StaffRichMediaClient {
  uploadImage(image: File): Promise<StaffRichMediaImage>
}

/** Shared Staff transport for inserting a server-owned image into Rich Markdown. */
export function createStaffRichMediaClient(
  runtime: RuntimeConfig,
  options: {
    fetchImplementation?: typeof globalThis.fetch
    refreshSession?: () => Promise<unknown>
  } = {},
): StaffRichMediaClient {
  const configured = parseRuntimeConfigForAudience('staff', runtime)
  const fetchImplementation = options.fetchImplementation ?? globalThis.fetch

  return {
    async uploadImage(image) {
      const body = new FormData()
      body.append('image', image, image.name)
      const send = () =>
        fetchImplementation(`${configured.apiBase}/rich-media/uploads`, {
          method: 'POST',
          body,
          cache: 'no-store',
          credentials: 'include',
          redirect: 'error',
          // Do not set Content-Type: the browser must add the multipart boundary.
          headers: { Accept: 'application/json' },
        })
      let response = await send()
      if (response.status === 401 && options.refreshSession) {
        await response.body?.cancel()
        await options.refreshSession()
        response = await send()
      }
      const payload: unknown = await response.json()
      if (!response.ok) throw new ApiResponseError(response.status, apiErrorSchema.parse(payload))
      return staffRichMediaUploadResponseSchema.parse(payload).image
    },
  }
}
