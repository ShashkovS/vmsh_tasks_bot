export const immutableContentAssetPathPrefix = '/pwa-content-assets/' as const
export const immutableContentAssetNavigationPattern = /^\/pwa-content-assets(?:\/|$)/

// Public nginx object routes, including the media relay introduced during the
// FirstVDS cutover; docs/deploy/firstvds-cutover-20261117/STATUS.md.
const publicObjectKeyPrefixes = [
  '/content/', '/image-uploads/', '/sol_imgs/', '/rich-files/',
  '/organizer-questions/', '/support-questions/',
]

export interface RecentMediaRequest {
  method: string
  destination: string
  url: URL
  applicationOrigin: string
  audienceGeneratedMediaPrefix: string
  publicMediaOrigin?: string | undefined
}

/**
 * Shared Student/Family Workbox boundary for immutable lesson media. See the
 * Phase-2 asset contract in `dev/development-plan/06-phase-2-content.md`.
 */
export function shouldCacheRecentMediaRequest(request: RecentMediaRequest): boolean {
  if (request.method !== 'GET' || request.destination !== 'image') return false
  const sameOrigin = request.url.origin === request.applicationOrigin
  if (sameOrigin) {
    return request.url.pathname.startsWith(immutableContentAssetPathPrefix) ||
      request.url.pathname.startsWith(request.audienceGeneratedMediaPrefix) ||
      publicObjectKeyPrefixes.some((prefix) => request.url.pathname.startsWith(prefix))
  }
  return Boolean(request.publicMediaOrigin) && request.url.origin === request.publicMediaOrigin
}
