import { pwaFetch } from '@vmsh/contracts'
import { t } from '@lingui/core/macro'
import { useQuery } from '@tanstack/react-query'
import {
  ApiResponseError,
  apiErrorSchema,
  lessonBlockPositionSchema,
  lessonBlockQueryKeys,
  publishLessonBlockRequestSchema,
  saveLessonBlockDraftRequestSchema,
  staffLessonBlocksResponseSchema,
  parseRuntimeConfigForAudience,
  publicIdSchema,
  type LessonBlockPosition,
  type PublishLessonBlockRequest,
  type RuntimeConfig,
  type SaveLessonBlockDraftRequest,
  type StaffLessonBlocksResponse,
} from '@vmsh/contracts'

export interface LessonBlockClient {
  get(groupLessonId: string, signal?: AbortSignal): Promise<StaffLessonBlocksResponse>
  save(
    groupLessonId: string,
    position: LessonBlockPosition,
    etag: string,
    input: SaveLessonBlockDraftRequest,
  ): Promise<void>
  publish(
    groupLessonId: string,
    position: LessonBlockPosition,
    etag: string,
    input: PublishLessonBlockRequest,
  ): Promise<void>
  hide(groupLessonId: string, position: LessonBlockPosition, etag: string): Promise<void>
  cancel(groupLessonId: string, position: LessonBlockPosition, etag: string): Promise<void>
  uploadImage(groupLessonId: string, image: File): Promise<{ url: string }>
}

export function createLessonBlockClient(
  runtime: RuntimeConfig,
  options: {
    refreshSession?: () => Promise<unknown>
    fetchImplementation?: typeof globalThis.fetch
  } = {},
): LessonBlockClient {
  const parsedRuntime = parseRuntimeConfigForAudience('staff', runtime)
  const fetchImplementation = options.fetchImplementation ?? pwaFetch
  const request = async <T>(
    path: string,
    method: string,
    parser: { parse(value: unknown): T } | null,
    etag?: string,
    body?: unknown,
    signal?: AbortSignal,
  ): Promise<T | void> => {
    const send = () =>
      fetchImplementation(`${parsedRuntime.apiBase}${path}`, {
        method,
        cache: 'no-store',
        credentials: 'include',
        redirect: 'error',
        headers: {
          Accept: 'application/json',
          ...(etag ? { 'If-Match': etag } : {}),
          ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
        },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
        ...(signal === undefined ? {} : { signal }),
      })
    let response = await send()
    if (response.status === 401 && options.refreshSession) {
      await response.body?.cancel()
      await options.refreshSession()
      response = await send()
    }
    if (!response.ok) {
      let value: unknown = null
      try {
        value = await response.json()
      } catch {
        /* preserve a typed transport error */
      }
      throw new ApiResponseError(response.status, apiErrorSchema.parse(value))
    }
    if (parser === null) return
    return parser.parse(await response.json())
  }
  const path = (groupLessonId: string, position?: LessonBlockPosition) => {
    const id = encodeURIComponent(publicIdSchema.parse(groupLessonId))
    return `/group-lessons/${id}/blocks${position ? `/${lessonBlockPositionSchema.parse(position)}` : ''}`
  }
  const uploadImage = async (groupLessonId: string, image: File): Promise<{ url: string }> => {
    const body = new FormData()
    body.set('image', image)
    const send = () =>
      fetchImplementation(`${parsedRuntime.apiBase}${path(groupLessonId)}/media/uploads`, {
        method: 'POST',
        cache: 'no-store',
        credentials: 'include',
        redirect: 'error',
        headers: { Accept: 'application/json' },
        body,
      })
    let response = await send()
    if (response.status === 401 && options.refreshSession) {
      await response.body?.cancel()
      await options.refreshSession()
      response = await send()
    }
    if (!response.ok) {
      let value: unknown = null
      try {
        value = await response.json()
      } catch {
        /* preserve a typed transport error */
      }
      throw new ApiResponseError(response.status, apiErrorSchema.parse(value))
    }
    const value: unknown = await response.json()
    const imageValue =
      value !== null && typeof value === 'object' && 'image' in value ? value.image : undefined
    if (
      !imageValue ||
      typeof imageValue !== 'object' ||
      !('url' in imageValue) ||
      typeof imageValue.url !== 'string'
    ) {
      throw new Error(t`Сервер вернул некорректный адрес изображения`)
    }
    return { url: imageValue.url }
  }
  return {
    get: (groupLessonId, signal) =>
      request(
        path(groupLessonId),
        'GET',
        staffLessonBlocksResponseSchema,
        undefined,
        undefined,
        signal,
      ) as Promise<StaffLessonBlocksResponse>,
    save: (groupLessonId, position, etag, input) =>
      request(
        `${path(groupLessonId, position)}/draft`,
        'PUT',
        null,
        etag,
        saveLessonBlockDraftRequestSchema.parse(input),
      ),
    publish: (groupLessonId, position, etag, input) =>
      request(
        `${path(groupLessonId, position)}/publication`,
        'POST',
        null,
        etag,
        publishLessonBlockRequestSchema.parse(input),
      ),
    hide: (groupLessonId, position, etag) =>
      request(`${path(groupLessonId, position)}/publication`, 'DELETE', null, etag),
    cancel: (groupLessonId, position, etag) =>
      request(`${path(groupLessonId, position)}/pending-publication`, 'DELETE', null, etag),
    uploadImage,
  }
}

export function useStaffLessonBlocksQuery(client: LessonBlockClient, groupLessonId: string) {
  return useQuery({
    queryKey: lessonBlockQueryKeys.staff(groupLessonId),
    queryFn: ({ signal }) => client.get(groupLessonId, signal),
  })
}
