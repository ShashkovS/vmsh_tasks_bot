export const immutableContentAssetPathPrefix = '/pwa-content-assets/' as const
export const immutableContentAssetNavigationPattern = /^\/pwa-content-assets(?:\/|$)/

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
  if (
    sameOrigin &&
    (request.url.pathname.startsWith(immutableContentAssetPathPrefix) ||
      request.url.pathname.startsWith(request.audienceGeneratedMediaPrefix))
  ) {
    return true
  }
  return Boolean(request.publicMediaOrigin) && request.url.origin === request.publicMediaOrigin
}
