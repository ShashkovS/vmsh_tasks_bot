import { nativePushPayloadSchema, type Audience, type NativePushPayload } from '@vmsh/contracts'

export function parseAudiencePushPayload(
  raw: string,
  audience: Audience,
): NativePushPayload | null {
  try {
    const parsed = nativePushPayloadSchema.safeParse(JSON.parse(raw))
    if (!parsed.success || !parsed.data.route.startsWith(`/${audience}/`)) return null
    return parsed.data
  } catch {
    return null
  }
}

export function isAudienceRoute(route: unknown, audience: Audience): route is string {
  return typeof route === 'string' && route.startsWith(`/${audience}/`)
}

/** Open directly within notificationclick activation; see docs/notification-activation.md.
 * Chrome Android may reuse the installed PWA. Do not await a background tab's navigation first.
 */
export async function openPushNotification(
  clients: { openWindow: (url: string) => Promise<{ focus: () => Promise<unknown> } | null> },
  origin: string,
  audience: Audience,
  data: unknown,
): Promise<void> {
  const route = typeof data === 'object' && data !== null && 'route' in data ? data.route : null
  if (!isAudienceRoute(route, audience)) return
  const target = new URL(route, origin)
  if (target.origin !== origin || !target.pathname.startsWith(`/${audience}/`)) return
  const opened = await clients.openWindow(target.href)
  // The navigation already succeeded if the platform cannot additionally focus it.
  if (opened) await opened.focus().catch(() => undefined)
}
