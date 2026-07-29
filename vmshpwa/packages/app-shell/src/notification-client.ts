import { useQuery } from '@tanstack/react-query'

import {
  ApiResponseError,
  acknowledgeNotificationRequestSchema,
  acknowledgeNotificationResponseSchema,
  apiErrorSchema,
  deletePushSubscriptionRequestSchema,
  deletePushSubscriptionResponseSchema,
  notificationEventListResponseSchema,
  notificationPreferenceListResponseSchema,
  notificationPreferenceResponseSchema,
  notificationQueryKeys,
  parseRuntimeConfigForAudience,
  publicIdSchema,
  pushSubscriptionConfigResponseSchema,
  savePushSubscriptionRequestSchema,
  savePushSubscriptionResponseSchema,
  updateNotificationPreferenceRequestSchema,
  type AcknowledgeNotificationResponse,
  type DeletePushSubscriptionResponse,
  type NotificationEventListResponse,
  type NotificationPreferenceListResponse,
  type NotificationPreferenceResponse,
  type PrincipalQueryScope,
  type PushSubscriptionConfigResponse,
  type RuntimeConfig,
  type SavePushSubscriptionRequest,
  type SavePushSubscriptionResponse,
  type UpdateNotificationPreferenceRequest,
} from '@vmsh/contracts'

type NotificationAudience = 'student' | 'family'

export interface NotificationClient {
  events(options?: {
    limit?: number
    unreadOnly?: boolean
    signal?: AbortSignal
  }): Promise<NotificationEventListResponse>
  preferences(options?: { signal?: AbortSignal }): Promise<NotificationPreferenceListResponse>
  updatePreference(
    request: UpdateNotificationPreferenceRequest,
  ): Promise<NotificationPreferenceResponse>
  acknowledge(eventId: string): Promise<AcknowledgeNotificationResponse>
  pushConfig(options?: { signal?: AbortSignal }): Promise<PushSubscriptionConfigResponse>
  savePushSubscription(request: SavePushSubscriptionRequest): Promise<SavePushSubscriptionResponse>
  deletePushSubscription(endpoint: string): Promise<DeletePushSubscriptionResponse>
}

export function createNotificationClient(
  runtime: RuntimeConfig,
  audience: NotificationAudience,
  options: {
    fetchImplementation?: typeof globalThis.fetch
    refreshSession?: () => Promise<unknown>
  } = {},
): NotificationClient {
  const configured = parseRuntimeConfigForAudience(audience, runtime)
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
    async events({ limit = 50, unreadOnly = false, signal } = {}) {
      const query = new URLSearchParams({ limit: String(limit), unreadOnly: String(unreadOnly) })
      return notificationEventListResponseSchema.parse(
        await request(`/notification-events?${query}`, {
          method: 'GET',
          ...(signal === undefined ? {} : { signal }),
        }),
      )
    },
    async preferences({ signal } = {}) {
      return notificationPreferenceListResponseSchema.parse(
        await request('/notifications/preferences', {
          method: 'GET',
          ...(signal === undefined ? {} : { signal }),
        }),
      )
    },
    async updatePreference(input) {
      const body = updateNotificationPreferenceRequestSchema.parse(input)
      return notificationPreferenceResponseSchema.parse(
        await request('/notifications/preferences', {
          method: 'PUT',
          body: JSON.stringify(body),
        }),
      )
    },
    async acknowledge(rawEventId) {
      const eventId = publicIdSchema.parse(rawEventId)
      const body = acknowledgeNotificationRequestSchema.parse({ schemaVersion: 1 })
      return acknowledgeNotificationResponseSchema.parse(
        await request(`/notification-events/${encodeURIComponent(eventId)}/read`, {
          method: 'POST',
          body: JSON.stringify(body),
        }),
      )
    },
    async pushConfig({ signal } = {}) {
      return pushSubscriptionConfigResponseSchema.parse(
        await request('/push-subscriptions/config', {
          method: 'GET',
          ...(signal === undefined ? {} : { signal }),
        }),
      )
    },
    async savePushSubscription(input) {
      const body = savePushSubscriptionRequestSchema.parse(input)
      return savePushSubscriptionResponseSchema.parse(
        await request('/push-subscriptions', {
          method: 'POST',
          body: JSON.stringify(body),
        }),
      )
    },
    async deletePushSubscription(endpoint) {
      const body = deletePushSubscriptionRequestSchema.parse({ schemaVersion: 1, endpoint })
      return deletePushSubscriptionResponseSchema.parse(
        await request('/push-subscriptions', {
          method: 'DELETE',
          body: JSON.stringify(body),
        }),
      )
    },
  }
}

export function useNotificationEventsQuery(
  client: NotificationClient,
  principal: PrincipalQueryScope,
  unreadOnly = false,
) {
  return useQuery({
    queryKey: notificationQueryKeys.events(principal, unreadOnly),
    queryFn: ({ signal }) => client.events({ unreadOnly, signal }),
    meta: { realtimeResources: ['notification-events'] },
  })
}

export function useNotificationPreferencesQuery(
  client: NotificationClient,
  principal: PrincipalQueryScope,
) {
  return useQuery({
    queryKey: notificationQueryKeys.preferences(principal),
    queryFn: ({ signal }) => client.preferences({ signal }),
    meta: { realtimeResources: ['notification-preferences'] },
  })
}

export function usePushSubscriptionConfigQuery(
  client: NotificationClient,
  principal: PrincipalQueryScope,
) {
  return useQuery({
    queryKey: notificationQueryKeys.pushConfig(principal),
    queryFn: ({ signal }) => client.pushConfig({ signal }),
  })
}
