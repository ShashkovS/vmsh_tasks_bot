import { ImageUploadClient, preparedImageMetadata } from './image-upload-client'
import { pwaFetch } from '@vmsh/contracts'
import {
  ApiResponseError,
  apiErrorSchema,
  parseRuntimeConfigForAudience,
  staffRichMediaUploadResponseSchema,
  type RuntimeConfig,
  type StaffRichMediaImage,
  type StaffRichFile,
} from '@vmsh/contracts'

import { uploadRichFile } from './rich-file-upload'

export interface StaffRichMediaClient {
  uploadImage(image: File): Promise<StaffRichMediaImage>
  uploadFile(file: File): Promise<StaffRichFile>
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
  const fetchImplementation = options.fetchImplementation ?? pwaFetch
  const images = new ImageUploadClient(runtime, 'rich', {}, options)

  return {
    uploadFile: (file) =>
      uploadRichFile(`${configured.apiBase}/rich-media/files/uploads`, file, options),
    async uploadImage(image) {
      const prepared = await images.preparePhoto(image)
      const metadata = preparedImageMetadata(prepared)
      const body = new FormData()
      body.append('image', prepared, metadata?.filename ?? image.name)
      const proxy = async (headers: Record<string, string> = {}) => {
        const send = () =>
          fetchImplementation(`${configured.apiBase}/rich-media/uploads`, {
            method: 'POST',
            body,
            cache: 'no-store',
            credentials: 'include',
            redirect: 'error',
            // Do not set Content-Type: the browser must add the multipart boundary.
            headers: { Accept: 'application/json', ...headers },
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
      }
      return metadata
        ? images.upload(
            prepared,
            metadata,
            '/rich-media/uploads',
            (payload) => staffRichMediaUploadResponseSchema.parse(payload).image,
            proxy,
          )
        : proxy()
    },
  }
}
