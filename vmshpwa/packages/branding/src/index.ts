import {
  brandProfile,
  brandingCacheName,
  brandAssetBase,
  brandingSelectionSchema,
  type BrandProfile,
  type BrandingSelection,
} from '@vmsh/contracts'
import { bootstrapLocale, type CatalogLoaders } from '@vmsh/i18n'

const cacheKey = 'vmsh:branding:v1'

export async function fetchBranding(
  audience: string,
  signal?: AbortSignal,
): Promise<BrandingSelection> {
  const response = await fetch(`/${audience}/api/v1/branding`, {
    credentials: 'same-origin',
    cache: 'no-store',
    ...(signal ? { signal } : {}),
  })
  if (!response.ok) throw new Error(`Branding request failed: ${response.status}`)
  return brandingSelectionSchema.parse(await response.json())
}

/** Resolves identity before locale/render; cached selection is only an offline fallback.
 * All profile assets are precached by both PWAs. See docs/branding.md.
 */
export async function bootstrapBranding(
  audience: string,
  loaders: CatalogLoaders,
): Promise<BrandProfile> {
  let selection: BrandingSelection
  try {
    selection = await fetchBranding(
      audience === 'landing' ? 'student' : audience,
      AbortSignal.timeout(5000),
    )
    try {
      window.localStorage.setItem(cacheKey, JSON.stringify(selection))
    } catch {
      /* Storage may be disabled. */
    }
  } catch (error) {
    // Never cache an invalid server payload or mask authorization/server errors.
    if (!(
      error instanceof TypeError ||
      (error instanceof DOMException && ['TimeoutError', 'AbortError'].includes(error.name))
    ))
      throw error
    let value: unknown = null
    try {
      value = JSON.parse(window.localStorage.getItem(cacheKey) ?? 'null')
    } catch {
      /* No usable offline copy. */
    }
    const cached = brandingSelectionSchema.safeParse(value)
    if (!cached.success) throw error
    selection = cached.data
  }
  // Make the same public selection available to offline push notifications.
  const cacheAudience = audience === 'landing' ? 'student' : audience
  if (typeof caches !== 'undefined') {
    void caches
      .open(brandingCacheName(cacheAudience))
      .then((cache) =>
        cache.put(
          `/${cacheAudience}/api/v1/branding`,
          new Response(JSON.stringify(selection), {
            headers: { 'Content-Type': 'application/json' },
          }),
        ),
      )
      .catch(() => {
        /* CacheStorage is optional; localStorage already supports UI fallback. */
      })
  }
  const profile = brandProfile(selection.profileId)
  document.documentElement.dataset.brand = profile.id
  const assets = brandAssetBase(profile, audience)
  document.querySelector('link[rel="icon"]')?.setAttribute('href', `${assets}icon.svg`)
  document
    .querySelector('link[rel="apple-touch-icon"]')
    ?.setAttribute('href', `${assets}icon-192.png`)
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', profile.themeColor)
  document.querySelector('meta[name="description"]')?.setAttribute('content', profile.name)
  const locale = await bootstrapLocale(loaders, profile.defaultLocale)
  return { ...profile, name: locale === 'en' ? profile.englishName : profile.name }
}
