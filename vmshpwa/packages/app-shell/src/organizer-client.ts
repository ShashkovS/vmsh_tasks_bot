import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ApiResponseError,
  apiErrorSchema,
  organizerListSchema,
  organizerThreadSchema,
  organizerSendSchema,
  organizerSentSchema,
  organizerUploadedSchema,
  type OrganizerSend,
  type RuntimeConfig,
} from '@vmsh/contracts'
import { useAuthentication } from './auth-context'

export function createOrganizerClient(runtime: RuntimeConfig, refresh: () => Promise<unknown>) {
  const base = `${runtime.apiBase}/organizer-questions`
  async function request(path: string, body?: unknown, photo?: Blob) {
    const send = () =>
      fetch(`${base}${path}`, {
        credentials: 'include',
        cache: 'no-store',
        redirect: 'error',
        method: body !== undefined || photo ? 'POST' : 'GET',
        headers: photo
          ? { 'Content-Type': photo.type }
          : body !== undefined
            ? { 'Content-Type': 'application/json' }
            : {},
        ...(photo ? { body: photo } : body !== undefined ? { body: JSON.stringify(body) } : {}),
      })
    let r = await send()
    if (r.status === 401) {
      await r.body?.cancel()
      await refresh()
      r = await send()
    }
    const data: unknown = await r.json()
    if (!r.ok) throw new ApiResponseError(r.status, apiErrorSchema.parse(data))
    return data
  }
  return {
    list: async (state = 'all', cursor?: string) =>
      organizerListSchema.parse(
        await request(`?state=${state}${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`),
      ),
    thread: async (id: string, cursor?: string) =>
      organizerThreadSchema.parse(
        await request(
          `/${encodeURIComponent(id)}${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ''}`,
        ),
      ),
    send: async (id: string | undefined, payload: OrganizerSend) =>
      organizerSentSchema.parse(
        await request(
          id ? `/${encodeURIComponent(id)}/entries` : '',
          organizerSendSchema.parse(payload),
        ),
      ),
    upload: async (photo: Blob) =>
      organizerUploadedSchema.parse(await request('/photos', undefined, photo)),
    read: async (id: string, sequence: number) =>
      request(`/${encodeURIComponent(id)}/read`, { sequence }),
  }
}
export function useOrganizerClient() {
  const auth = useAuthentication()
  return useMemo(
    () =>
      createOrganizerClient(auth.client.runtime, async () => {
        try {
          return await auth.refresh()
        } catch (error) {
          auth.handleApiError(error)
          throw error
        }
      }),
    [auth],
  )
}
export function useOrganizerCount(accountId: string) {
  const client = useOrganizerClient()
  return useQuery({
    queryKey: ['organizer-questions', accountId, 'count'],
    queryFn: async () => (await client.list()).unreadCount,
    meta: { realtimeResources: ['organizer-questions'] },
    refetchOnWindowFocus: 'always',
  })
}
