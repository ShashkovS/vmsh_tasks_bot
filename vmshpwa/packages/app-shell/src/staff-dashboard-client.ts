import { useQuery } from '@tanstack/react-query'

import {
  ApiResponseError,
  apiErrorSchema,
  parseRuntimeConfigForAudience,
  staffDashboardQueryKey,
  staffDashboardResponseSchema,
  type PrincipalQueryScope,
  type RuntimeConfig,
  type StaffDashboardResponse,
} from '@vmsh/contracts'

export interface StaffDashboardClient {
  get(signal?: AbortSignal): Promise<StaffDashboardResponse>
}

export function createStaffDashboardClient(
  runtime: RuntimeConfig,
  options: {
    fetchImplementation?: typeof globalThis.fetch
    refreshSession?: () => Promise<unknown>
  } = {},
): StaffDashboardClient {
  const configured = parseRuntimeConfigForAudience('staff', runtime)
  const fetchImplementation = options.fetchImplementation ?? globalThis.fetch

  return {
    async get(signal) {
      const request = () =>
        fetchImplementation(`${configured.apiBase}/dashboard`, {
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
      return staffDashboardResponseSchema.parse(payload)
    },
  }
}

export function useStaffDashboardQuery(
  client: StaffDashboardClient,
  principal: PrincipalQueryScope,
) {
  return useQuery({
    queryKey: staffDashboardQueryKey(principal),
    queryFn: ({ signal }) => client.get(signal),
  })
}
