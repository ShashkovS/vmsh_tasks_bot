import { describe, expect, it } from 'vitest'

import {
  immutableContentAssetNavigationPattern,
  immutableContentAssetPathPrefix,
  shouldCacheRecentMediaRequest,
} from './recent-media-policy'

const applicationOrigin = 'https://vmsh.example.test'

function matches(
  url: string,
  overrides: Partial<Parameters<typeof shouldCacheRecentMediaRequest>[0]> = {},
) {
  return shouldCacheRecentMediaRequest({
    method: 'GET',
    destination: 'image',
    url: new URL(url),
    applicationOrigin,
    audienceGeneratedMediaPrefix: '/student/media/generated/',
    publicMediaOrigin: 'https://assets.example.test',
    ...overrides,
  })
}

describe('recent media Workbox policy', () => {
  it('caches the audience-neutral immutable content namespace', () => {
    expect(immutableContentAssetPathPrefix).toBe('/pwa-content-assets/')
    expect(immutableContentAssetNavigationPattern.test('/pwa-content-assets/asset-179')).toBe(true)
    expect(matches(`${applicationOrigin}/pwa-content-assets/asset-179`)).toBe(true)
  })

  it('keeps non-images, writes and lookalike external paths out of the cache', () => {
    expect(
      matches(`${applicationOrigin}/pwa-content-assets/asset-179`, { destination: 'document' }),
    ).toBe(false)
    expect(matches(`${applicationOrigin}/pwa-content-assets/asset-179`, { method: 'POST' })).toBe(
      false,
    )
    expect(matches('https://attacker.example/pwa-content-assets/asset-179')).toBe(false)
    expect(matches('https://assets.example.test/content/asset-179')).toBe(true)
  })
})
