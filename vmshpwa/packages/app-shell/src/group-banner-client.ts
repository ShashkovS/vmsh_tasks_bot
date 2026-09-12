import { useQuery } from '@tanstack/react-query'

import {
  ApiResponseError,
  apiErrorSchema,
  cancelGroupBannerRequestSchema,
  groupBannerListResponseSchema,
  groupBannerQueryKeys,
  groupBannerResponseSchema,
  parseRuntimeConfigForAudience,
  publicIdSchema,
  saveGroupBannerRequestSchema,
  updateGroupBannerRequestSchema,
  type GroupBannerListResponse,
  type GroupBannerResponse,
  type PrincipalQueryScope,
  type RuntimeConfig,
  type SaveGroupBannerRequest,
  type UpdateGroupBannerRequest,
} from '@vmsh/contracts'

type BannerAudience = 'student' | 'family'

async function responsePayload(response: Response): Promise<unknown> {
  const payload: unknown = await response.json()
  if (!response.ok) throw new ApiResponseError(response.status, apiErrorSchema.parse(payload))
  return payload
}

function refreshableFetch(
  base: string,
  options: {
    fetchImplementation?: typeof globalThis.fetch
    refreshSession?: () => Promise<unknown>
  },
) {
  const fetchImplementation = options.fetchImplementation ?? globalThis.fetch
  return async (path: string, init: RequestInit): Promise<unknown> => {
    const send = () =>
      fetchImplementation(`${base}${path}`, {
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
    return responsePayload(response)
  }
}

export function createGroupBannerClient(
  runtime: RuntimeConfig,
  audience: BannerAudience,
  options: {
    fetchImplementation?: typeof globalThis.fetch
    refreshSession?: () => Promise<unknown>
  } = {},
) {
  const request = refreshableFetch(
    parseRuntimeConfigForAudience(audience, runtime).apiBase,
    options,
  )
  return {
    async active(signal?: AbortSignal): Promise<GroupBannerListResponse> {
      return groupBannerListResponseSchema.parse(
        await request('/banners/active?contentVersion=2', {
          method: 'GET',
          ...(signal === undefined ? {} : { signal }),
        }),
      )
    },
  }
}

export function createStaffGroupBannerClient(
  runtime: RuntimeConfig,
  options: {
    fetchImplementation?: typeof globalThis.fetch
    refreshSession?: () => Promise<unknown>
  } = {},
) {
  const request = refreshableFetch(parseRuntimeConfigForAudience('staff', runtime).apiBase, options)
  const mutation = (
    path: string,
    method: 'POST' | 'PATCH',
    body: object,
    etag?: string,
  ): Promise<GroupBannerResponse> =>
    request(path, {
      method,
      body: JSON.stringify(body),
      ...(etag === undefined ? {} : { headers: { 'If-Match': etag } }),
    }).then((payload) => groupBannerResponseSchema.parse(payload))
  return {
    async list(signal?: AbortSignal): Promise<GroupBannerListResponse> {
      return groupBannerListResponseSchema.parse(
        await request('/group-banners?limit=200&contentVersion=2', {
          method: 'GET',
          ...(signal === undefined ? {} : { signal }),
        }),
      )
    },
    create(input: SaveGroupBannerRequest) {
      return mutation('/group-banners', 'POST', saveGroupBannerRequestSchema.parse(input))
    },
    update(rawId: string, version: number, input: UpdateGroupBannerRequest) {
      const id = publicIdSchema.parse(rawId)
      return mutation(
        `/group-banners/${encodeURIComponent(id)}`,
        'PATCH',
        updateGroupBannerRequestSchema.parse(input),
        `"${id}:v${version}"`,
      )
    },
    cancel(rawId: string, version: number) {
      const id = publicIdSchema.parse(rawId)
      return mutation(
        `/group-banners/${encodeURIComponent(id)}/cancel`,
        'POST',
        cancelGroupBannerRequestSchema.parse({ schemaVersion: 1 }),
        `"${id}:v${version}"`,
      )
    },
  }
}

export function useActiveGroupBannersQuery(
  client: ReturnType<typeof createGroupBannerClient>,
  principal: PrincipalQueryScope,
) {
  return useQuery({
    queryKey: groupBannerQueryKeys.active(principal),
    queryFn: ({ signal }) => client.active(signal),
    meta: { realtimeResources: ['banners'] },
  })
}

export function useStaffGroupBannersQuery(
  client: ReturnType<typeof createStaffGroupBannerClient>,
  principal: PrincipalQueryScope,
) {
  return useQuery({
    queryKey: groupBannerQueryKeys.staff(principal),
    queryFn: ({ signal }) => client.list(signal),
    meta: { realtimeResources: ['banners'] },
  })
}
