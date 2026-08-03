import { useQuery } from '@tanstack/react-query'

import {
  ApiResponseError,
  apiErrorSchema,
  changeNewsVisibilityRequestSchema,
  createLocalNewsRequestSchema,
  newsQueryKeys,
  parseRuntimeConfigForAudience,
  publicIdSchema,
  reconcileNewsSourceRequestSchema,
  staffNewsItemResponseSchema,
  staffNewsListResponseSchema,
  staffNewsVisibilityFilterSchema,
  updateLocalNewsRequestSchema,
  type ChangeNewsVisibilityRequest,
  type CreateLocalNewsRequest,
  type PrincipalQueryScope,
  type ReconcileNewsSourceRequest,
  type RuntimeConfig,
  type StaffNewsItemResponse,
  type StaffNewsListResponse,
  type StaffNewsVisibilityFilter,
  type UpdateLocalNewsRequest,
} from '@vmsh/contracts'

export interface NewsModerationClient {
  list(
    state: StaffNewsVisibilityFilter,
    options?: { signal?: AbortSignal },
  ): Promise<StaffNewsListResponse>
  createLocal(request: CreateLocalNewsRequest): Promise<StaffNewsItemResponse>
  updateLocal(
    postId: string,
    version: number,
    request: UpdateLocalNewsRequest,
  ): Promise<StaffNewsItemResponse>
  changeVisibility(
    postId: string,
    version: number,
    request: ChangeNewsVisibilityRequest,
  ): Promise<StaffNewsItemResponse>
  reconcileSource(
    postId: string,
    version: number,
    request: ReconcileNewsSourceRequest,
  ): Promise<StaffNewsItemResponse>
}

/** Admin-only transport for the narrow PWA news moderation workflow. */
export function createNewsModerationClient(
  runtime: RuntimeConfig,
  options: {
    fetchImplementation?: typeof globalThis.fetch
    refreshSession?: () => Promise<unknown>
  } = {},
): NewsModerationClient {
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

  return {
    async list(rawState, { signal } = {}) {
      const state = staffNewsVisibilityFilterSchema.parse(rawState)
      return staffNewsListResponseSchema.parse(
        await request(`/news?state=${state}&limit=100`, {
          method: 'GET',
          ...(signal === undefined ? {} : { signal }),
        }),
      )
    },
    async createLocal(input) {
      const body = createLocalNewsRequestSchema.parse(input)
      return staffNewsItemResponseSchema.parse(
        await request('/news/local', {
          method: 'POST',
          body: JSON.stringify(body),
        }),
      )
    },
    async updateLocal(rawPostId, version, input) {
      const postId = publicIdSchema.parse(rawPostId)
      const body = updateLocalNewsRequestSchema.parse(input)
      return staffNewsItemResponseSchema.parse(
        await request(`/news/${encodeURIComponent(postId)}/local`, {
          method: 'PATCH',
          headers: { 'If-Match': `"${postId}:v${version}"` },
          body: JSON.stringify(body),
        }),
      )
    },
    async changeVisibility(rawPostId, version, input) {
      const postId = publicIdSchema.parse(rawPostId)
      const body = changeNewsVisibilityRequestSchema.parse(input)
      return staffNewsItemResponseSchema.parse(
        await request(`/news/${encodeURIComponent(postId)}/visibility`, {
          method: 'PATCH',
          headers: { 'If-Match': `"${postId}:v${version}"` },
          body: JSON.stringify(body),
        }),
      )
    },
    async reconcileSource(rawPostId, version, input) {
      const postId = publicIdSchema.parse(rawPostId)
      const body = reconcileNewsSourceRequestSchema.parse(input)
      return staffNewsItemResponseSchema.parse(
        await request(`/news/${encodeURIComponent(postId)}/source-state`, {
          method: 'PATCH',
          headers: { 'If-Match': `"${postId}:v${version}"` },
          body: JSON.stringify(body),
        }),
      )
    },
  }
}

export function useNewsModerationQuery(
  client: NewsModerationClient,
  principal: PrincipalQueryScope,
  state: StaffNewsVisibilityFilter,
) {
  return useQuery({
    queryKey: newsQueryKeys.moderation(principal, state),
    queryFn: ({ signal }) => client.list(state, { signal }),
    meta: { realtimeResources: ['news'] },
  })
}
