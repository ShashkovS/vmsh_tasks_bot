import {
  pwaFetch,
  ApiResponseError,
  apiErrorSchema,
  staffRichFileUploadResponseSchema,
} from '@vmsh/contracts'

/** Common multipart transport for both permission-scoped file upload APIs. */
export async function uploadRichFile(
  url: string,
  file: File,
  options: {
    fetchImplementation?: typeof globalThis.fetch
    refreshSession?: () => Promise<unknown>
  },
) {
  const body = new FormData()
  body.append('file', file, file.name)
  const send = () =>
    (options.fetchImplementation ?? pwaFetch)(url, {
      method: 'POST',
      body,
      cache: 'no-store',
      credentials: 'include',
      redirect: 'error',
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
  return staffRichFileUploadResponseSchema.parse(payload).file
}
