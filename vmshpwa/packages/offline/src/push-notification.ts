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
