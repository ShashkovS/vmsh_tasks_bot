import { useQuery } from '@tanstack/react-query'

import {
  ApiResponseError,
  apiErrorSchema,
  oralWindowQueryKeys,
  parseRuntimeConfigForAudience,
  publicIdSchema,
  saveOralWindowRequestSchema,
  staffOralWindowListResponseSchema,
  staffOralWindowResponseSchema,
  type PrincipalQueryScope,
  type RuntimeConfig,
  type SaveOralWindowRequest,
  type StaffOralWindowListResponse,
  type StaffOralWindowResponse,
} from '@vmsh/contracts'

export function createStaffOralWindowClient(
  runtime: RuntimeConfig,
  options: {
    fetchImplementation?: typeof globalThis.fetch
    refreshSession?: () => Promise<unknown>
  } = {},
) {
  const base = parseRuntimeConfigForAudience('staff', runtime).apiBase
  const fetchImplementation = options.fetchImplementation ?? globalThis.fetch

  const request = async (path: string, init: RequestInit): Promise<unknown> => {
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
    const payload: unknown = await response.json()
    if (!response.ok) throw new ApiResponseError(response.status, apiErrorSchema.parse(payload))
    return payload
  }

  return {
    async list(groupLessonId: string, signal?: AbortSignal): Promise<StaffOralWindowListResponse> {
      const lessonId = publicIdSchema.parse(groupLessonId)
      return staffOralWindowListResponseSchema.parse(
        await request(`/group-lessons/${encodeURIComponent(lessonId)}/oral-windows`, {
          method: 'GET',
          ...(signal === undefined ? {} : { signal }),
        }),
      )
    },
    async create(
      groupLessonId: string,
      input: SaveOralWindowRequest,
    ): Promise<StaffOralWindowResponse> {
      const lessonId = publicIdSchema.parse(groupLessonId)
      return staffOralWindowResponseSchema.parse(
        await request(`/group-lessons/${encodeURIComponent(lessonId)}/oral-windows`, {
          method: 'POST',
          body: JSON.stringify(saveOralWindowRequestSchema.parse(input)),
        }),
      )
    },
    async update(
      windowId: string,
      version: number,
      input: SaveOralWindowRequest,
    ): Promise<StaffOralWindowResponse> {
      const parsedWindowId = publicIdSchema.parse(windowId)
      return staffOralWindowResponseSchema.parse(
        await request(`/oral-windows/${encodeURIComponent(parsedWindowId)}`, {
          method: 'PUT',
          body: JSON.stringify(saveOralWindowRequestSchema.parse(input)),
          headers: { 'If-Match': `"${parsedWindowId}:v${version}"` },
        }),
      )
    },
  }
}

export function useStaffOralWindowsQuery(
  client: ReturnType<typeof createStaffOralWindowClient>,
  principal: PrincipalQueryScope,
  groupLessonId: string,
  enabled = true,
) {
  return useQuery({
    enabled,
    queryKey: oralWindowQueryKeys.staff(principal, groupLessonId),
    queryFn: ({ signal }) => client.list(groupLessonId, signal),
    meta: { realtimeResources: ['oral-windows'] },
  })
}
