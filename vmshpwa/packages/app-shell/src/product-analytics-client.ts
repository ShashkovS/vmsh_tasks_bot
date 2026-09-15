import { useQuery } from '@tanstack/react-query'
import {
  ApiResponseError,
  apiErrorSchema,
  productAnalyticsEventsSchema,
  productAnalyticsSummarySchema,
  type ProductAnalyticsEvents,
  type ProductAnalyticsSummary,
  type RuntimeConfig,
} from '@vmsh/contracts'

export interface ProductAnalyticsFilter {
  from: string
  to: string
  audience?: string
  accountId?: string
  eventType?: string
}

export function createProductAnalyticsClient(runtime: RuntimeConfig) {
  const get = async <T>(path: string, schema: { parse(value: unknown): T }): Promise<T> => {
    const response = await fetch(`${runtime.apiBase}${path}`, {
      credentials: 'include', cache: 'no-store', headers: { Accept: 'application/json' },
    })
    const payload: unknown = await response.json()
    if (!response.ok) throw new ApiResponseError(response.status, apiErrorSchema.parse(payload))
    return schema.parse(payload)
  }
  const search = (filter: ProductAnalyticsFilter) => {
    const params = new URLSearchParams({ from: filter.from, to: filter.to })
    if (filter.audience) params.set('audience', filter.audience)
    if (filter.accountId) params.set('accountId', filter.accountId)
    if (filter.eventType) params.set('eventType', filter.eventType)
    return params.toString()
  }
  return {
    summary: (filter: ProductAnalyticsFilter): Promise<ProductAnalyticsSummary> =>
      get(`/analytics/summary?${search(filter)}`, productAnalyticsSummarySchema),
    events: (filter: ProductAnalyticsFilter): Promise<ProductAnalyticsEvents> =>
      get(`/analytics/events?${search(filter)}`, productAnalyticsEventsSchema),
  }
}

export function useProductAnalyticsSummary(
  client: ReturnType<typeof createProductAnalyticsClient>, filter: ProductAnalyticsFilter,
) {
  return useQuery({ queryKey: ['product-analytics', 'summary', filter], queryFn: () => client.summary(filter) })
}

export function useProductAnalyticsEvents(
  client: ReturnType<typeof createProductAnalyticsClient>, filter: ProductAnalyticsFilter,
) {
  return useQuery({ queryKey: ['product-analytics', 'events', filter], queryFn: () => client.events(filter) })
}
