import { useInfiniteQuery, useQuery } from '@tanstack/react-query'

import {
  ApiResponseError,
  apiErrorSchema,
  newsFeedResponseSchema,
  newsPostResponseSchema,
  newsQueryKeys,
  parseRuntimeConfigForAudience,
  publicIdSchema,
  type NewsFeedResponse,
  type NewsPostResponse,
  type PrincipalQueryScope,
  type RuntimeConfig,
} from '@vmsh/contracts'

type NewsAudience = 'student' | 'family'

export interface NewsClient {
  list(options?: {
    cursor?: string
    limit?: number
    signal?: AbortSignal
  }): Promise<NewsFeedResponse>
  post(postId: string, options?: { signal?: AbortSignal }): Promise<NewsPostResponse>
}

/** Authenticated Student/Family transport for Phase 8 news reads. */
export function createNewsClient(
  runtime: RuntimeConfig,
  audience: NewsAudience,
  options: {
    fetchImplementation?: typeof globalThis.fetch
    refreshSession?: () => Promise<unknown>
  } = {},
): NewsClient {
  const configured = parseRuntimeConfigForAudience(audience, runtime)
  const fetchImplementation = options.fetchImplementation ?? globalThis.fetch

  async function request(path: string, signal?: AbortSignal): Promise<unknown> {
    const send = () =>
      fetchImplementation(`${configured.apiBase}${path}`, {
        method: 'GET',
        cache: 'no-store',
        credentials: 'include',
        headers: { Accept: 'application/json' },
        redirect: 'error',
        ...(signal === undefined ? {} : { signal }),
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
    async list({ cursor, limit = 20, signal } = {}) {
      const query = new URLSearchParams({ limit: String(limit) })
      if (cursor !== undefined) query.set('cursor', publicIdSchema.parse(cursor))
      return newsFeedResponseSchema.parse(await request(`/news?${query}`, signal))
    },
    async post(rawPostId, { signal } = {}) {
      const postId = publicIdSchema.parse(rawPostId)
      return newsPostResponseSchema.parse(
        await request(`/news/${encodeURIComponent(postId)}`, signal),
      )
    },
  }
}

export function useNewsFeedQuery(client: NewsClient, principal: PrincipalQueryScope) {
  return useInfiniteQuery({
    queryKey: newsQueryKeys.feed(principal),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) =>
      client.list({ ...(pageParam === null ? {} : { cursor: pageParam }), signal }),
    getNextPageParam: (page) => page.nextCursor ?? undefined,
    meta: { realtimeResources: ['news'] },
  })
}

export function useNewsPostQuery(
  client: NewsClient,
  principal: PrincipalQueryScope,
  postId: string,
) {
  return useQuery({
    queryKey: newsQueryKeys.post(principal, postId),
    queryFn: ({ signal }) => client.post(postId, { signal }),
    meta: { realtimeResources: ['news'] },
  })
}
