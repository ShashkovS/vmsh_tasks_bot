import { useQuery } from '@tanstack/react-query'

import {
  ApiResponseError,
  apiErrorSchema,
  auditListResponseSchema,
  auditObjectTypeSchema,
  auditQueryKeys,
  parseRuntimeConfigForAudience,
  publicIdSchema,
  type AuditListResponse,
  type AuditObjectType,
  type PrincipalQueryScope,
  type RuntimeConfig,
} from '@vmsh/contracts'

export interface AuditFilter {
  objectType: AuditObjectType
  query: string
  cursor: string | null
}

export interface AuditClient {
  list(filter: AuditFilter, signal?: AbortSignal): Promise<AuditListResponse>
}

export function createAuditClient(
  runtime: RuntimeConfig,
  options: {
    fetchImplementation?: typeof globalThis.fetch
    refreshSession?: () => Promise<unknown>
  } = {},
): AuditClient {
  const configured = parseRuntimeConfigForAudience('staff', runtime)
  const fetchImplementation = options.fetchImplementation ?? globalThis.fetch

  async function send(path: string, signal?: AbortSignal) {
    const request = () =>
      fetchImplementation(`${configured.apiBase}${path}`, {
        method: 'GET',
        cache: 'no-store',
        credentials: 'include',
        redirect: 'error',
        headers: { Accept: 'application/json' },
        ...(signal === undefined ? {} : { signal }),
      })
    let response = await request()
    if (response.status === 401 && options.refreshSession) {
      await response.body?.cancel()
      await options.refreshSession()
      response = await request()
    }
    const payload: unknown = await response.json()
    if (!response.ok) throw new ApiResponseError(response.status, apiErrorSchema.parse(payload))
    return payload
  }

  return {
    async list(rawFilter, signal) {
      const objectType = auditObjectTypeSchema.parse(rawFilter.objectType)
      const query = rawFilter.query.trim()
      if (query.length > 100) throw new Error('Audit query is too long')
      const cursor = rawFilter.cursor === null ? null : publicIdSchema.parse(rawFilter.cursor)
      const search = new URLSearchParams({ objectType, q: query, limit: '50' })
      if (cursor !== null) search.set('cursor', cursor)
      return auditListResponseSchema.parse(await send(`/audit?${search}`, signal))
    },
  }
}

export function useAuditQuery(
  client: AuditClient,
  principal: PrincipalQueryScope,
  filter: AuditFilter,
) {
  return useQuery({
    queryKey: auditQueryKeys.list(principal, filter),
    queryFn: ({ signal }) => client.list(filter, signal),
  })
}
