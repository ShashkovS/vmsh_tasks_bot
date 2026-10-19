import { afterEach, expect, it, vi } from 'vitest'
import { notificationBrandIcon } from './push-branding'
afterEach(() => vi.unstubAllGlobals())
it('uses the selected brand for notifications', async () => {
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ profileId: 'tlf-prep-clubs', version: 1 }))),
  )
  vi.stubGlobal('caches', { open: vi.fn().mockResolvedValue({ put: vi.fn() }) })
  expect(await notificationBrandIcon('student')).toBe(
    '/student/brands/tlf-prep-clubs/v1/icon-192.png',
  )
})
it('keeps a notification branded when only the cached selection is available', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))
  vi.stubGlobal('caches', {
    open: vi.fn().mockResolvedValue({
      match: vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify({ profileId: 'tlf-prep-clubs', version: 1 })),
        ),
    }),
  })
  expect(await notificationBrandIcon('family')).toBe(
    '/family/brands/tlf-prep-clubs/v1/icon-192.png',
  )
})
it('still displays notifications if storage and network are unavailable', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))
  vi.stubGlobal('caches', { open: vi.fn().mockRejectedValue(new Error('disabled')) })
  expect(await notificationBrandIcon('family')).toBe('/family/icon-192.png')
})
