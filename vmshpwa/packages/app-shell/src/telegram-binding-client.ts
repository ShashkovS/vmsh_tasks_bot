import { useQuery } from '@tanstack/react-query'

import {
  ApiResponseError,
  apiErrorSchema,
  changeTelegramBindingStatusRequestSchema,
  parseRuntimeConfigForAudience,
  principalQueryKey,
  publicIdSchema,
  saveTelegramBindingRequestSchema,
  telegramBindingListResponseSchema,
  telegramBindingOwnersResponseSchema,
  telegramBindingQueryKeys,
  telegramBindingResponseSchema,
  type PrincipalQueryScope,
  type RuntimeConfig,
  type SaveTelegramBindingRequest,
  type TelegramBindingListResponse,
  type TelegramBindingOwnersResponse,
  type TelegramBindingResponse,
} from '@vmsh/contracts'

export interface TelegramBindingClient {
  owners(options?: { signal?: AbortSignal }): Promise<TelegramBindingOwnersResponse>
  list(options?: { courseId?: string; signal?: AbortSignal }): Promise<TelegramBindingListResponse>
  create(request: SaveTelegramBindingRequest): Promise<TelegramBindingResponse>
  update(
    publicId: string,
    version: number,
    request: SaveTelegramBindingRequest,
  ): Promise<TelegramBindingResponse>
  disable(publicId: string, version: number): Promise<TelegramBindingResponse>
  restoreDraft(publicId: string, version: number): Promise<TelegramBindingResponse>
  verify(publicId: string, version: number): Promise<TelegramBindingResponse>
}

export function createTelegramBindingClient(
  runtime: RuntimeConfig,
  options: {
    fetchImplementation?: typeof globalThis.fetch
    refreshSession?: () => Promise<unknown>
  } = {},
): TelegramBindingClient {
  const configured = parseRuntimeConfigForAudience('staff', runtime)
  const fetchImplementation = options.fetchImplementation ?? globalThis.fetch

  async function request(path: string, init: RequestInit): Promise<unknown> {
    const send = () =>
      fetchImplementation(`${configured.apiBase}${path}`, {
        cache: 'no-store',
        credentials: 'include',
        redirect: 'error',
        ...init,
        headers: {
          Accept: 'application/json',
          ...(init.body === undefined ? {} : { 'Content-Type': 'application/json' }),
          ...init.headers,
        },
      })
    let response = await send()
    if (response.status === 401 && options.refreshSession) {
      await response.body?.cancel()
      await options.refreshSession()
      response = await send()
    }
    const payload: unknown = await response.json()
    if (!response.ok) throw new ApiResponseError(response.status, apiErrorSchema.parse(payload))
    return payload
  }

  function mutation(
    path: string,
    method: 'POST' | 'PUT',
    body: object,
    etag?: string,
  ): Promise<TelegramBindingResponse> {
    return request(path, {
      method,
      body: JSON.stringify(body),
      ...(etag === undefined ? {} : { headers: { 'If-Match': etag } }),
    }).then((payload) => telegramBindingResponseSchema.parse(payload))
  }

  return {
    async owners({ signal } = {}) {
      return telegramBindingOwnersResponseSchema.parse(
        await request('/telegram-binding-owners', {
          method: 'GET',
          ...(signal === undefined ? {} : { signal }),
        }),
      )
    },
    async list({ courseId, signal } = {}) {
      const query = new URLSearchParams()
      if (courseId !== undefined) query.set('courseId', publicIdSchema.parse(courseId))
      const suffix = query.size === 0 ? '' : `?${query}`
      return telegramBindingListResponseSchema.parse(
        await request(`/telegram-bindings${suffix}`, {
          method: 'GET',
          ...(signal === undefined ? {} : { signal }),
        }),
      )
    },
    create(input) {
      return mutation('/telegram-bindings', 'POST', saveTelegramBindingRequestSchema.parse(input))
    },
    update(rawPublicId, version, input) {
      const publicId = publicIdSchema.parse(rawPublicId)
      return mutation(
        `/telegram-bindings/${encodeURIComponent(publicId)}`,
        'PUT',
        saveTelegramBindingRequestSchema.parse(input),
        `"${publicId}:v${version}"`,
      )
    },
    disable(rawPublicId, version) {
      const publicId = publicIdSchema.parse(rawPublicId)
      return mutation(
        `/telegram-bindings/${encodeURIComponent(publicId)}/disable`,
        'POST',
        changeTelegramBindingStatusRequestSchema.parse({ schemaVersion: 1 }),
        `"${publicId}:v${version}"`,
      )
    },
    restoreDraft(rawPublicId, version) {
      const publicId = publicIdSchema.parse(rawPublicId)
      return mutation(
        `/telegram-bindings/${encodeURIComponent(publicId)}/restore-draft`,
        'POST',
        changeTelegramBindingStatusRequestSchema.parse({ schemaVersion: 1 }),
        `"${publicId}:v${version}"`,
      )
    },
    verify(rawPublicId, version) {
      const publicId = publicIdSchema.parse(rawPublicId)
      return mutation(
        `/telegram-bindings/${encodeURIComponent(publicId)}/verify`,
        'POST',
        changeTelegramBindingStatusRequestSchema.parse({ schemaVersion: 1 }),
        `"${publicId}:v${version}"`,
      )
    },
  }
}

export function useTelegramBindingsQuery(
  client: TelegramBindingClient,
  principal: PrincipalQueryScope,
  courseId?: string,
) {
  return useQuery({
    queryKey: telegramBindingQueryKeys.list(principal, courseId),
    queryFn: ({ signal }) => client.list({ ...(courseId ? { courseId } : {}), signal }),
  })
}

export function useTelegramBindingOwnersQuery(
  client: TelegramBindingClient,
  principal: PrincipalQueryScope,
) {
  return useQuery({
    queryKey: ['telegram-binding-owners', ...principalQueryKey(principal)],
    queryFn: ({ signal }) => client.owners({ signal }),
  })
}
