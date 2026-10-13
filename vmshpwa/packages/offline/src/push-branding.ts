import {
  brandAssetBase,
  brandProfile,
  brandingCacheName,
  brandingSelectionSchema,
} from '@vmsh/contracts'

/** Push uses the same reviewed identity as the UI; see docs/branding.md. */
export async function notificationBrandIcon(audience: 'student' | 'family'): Promise<string> {
  const url = `/${audience}/api/v1/branding`
  let response: Response | undefined
  try {
    const fresh = await fetch(url, {
      credentials: 'same-origin',
      cache: 'no-store',
      signal: AbortSignal.timeout(3000),
    })
    if (fresh.ok) {
      const selection = brandingSelectionSchema.parse(await fresh.clone().json())
      try {
        await (await caches.open(brandingCacheName(audience))).put(url, fresh)
      } catch {
        /* Cache is optional. */
      }
      return `${brandAssetBase(brandProfile(selection.profileId), audience)}icon-192.png`
    }
  } catch {
    /* Push must still be displayed when the network is unavailable. */
  }
  try {
    response = await (await caches.open(brandingCacheName(audience))).match(url)
  } catch {
    /* Cache may be disabled. */
  }
  if (response) {
    try {
      const selection = brandingSelectionSchema.parse(await response.json())
      return `${brandAssetBase(brandProfile(selection.profileId), audience)}icon-192.png`
    } catch {
      /* An old or corrupt entry cannot suppress a notification. */
    }
  }
  return `/${audience}/icon-192.png`
}
