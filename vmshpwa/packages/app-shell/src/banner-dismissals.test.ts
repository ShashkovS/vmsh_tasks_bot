import { describe, expect, it } from 'vitest'

import fixture from '@vmsh/contracts/fixtures/group-banners/list.v1.json'
import { groupBannerListResponseSchema } from '@vmsh/contracts'

import { bannerDismissalId, readDismissedBanners, writeDismissedBanner } from './banner-dismissals'

describe('device-local banner dismissals', () => {
  it('is account-scoped and reopens a changed banner version', () => {
    const values = new Map<string, string>()
    const storage = {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
    }
    const principal = { audience: 'student' as const, accountId: 'student-one' }
    const banner = groupBannerListResponseSchema.parse(fixture).items[0]!
    const dismissed = writeDismissedBanner(storage, principal, banner)
    expect(dismissed.has(bannerDismissalId(banner))).toBe(true)
    expect(readDismissedBanners(storage, { ...principal, accountId: 'student-two' }).size).toBe(0)
    expect(dismissed.has(bannerDismissalId({ ...banner, version: 2 }))).toBe(false)
  })
})
