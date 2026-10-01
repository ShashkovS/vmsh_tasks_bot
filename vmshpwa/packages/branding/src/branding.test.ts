import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { bootstrapBranding } from './index'
import { bootstrapLocale } from '@vmsh/i18n'
vi.mock('@vmsh/i18n', () => ({ bootstrapLocale: vi.fn().mockResolvedValue('en') }))
const loaders = { ru: vi.fn(), en: vi.fn() }
beforeEach(() => {
  vi.restoreAllMocks()
  const values = new Map<string, string>()
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    value: {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
    },
  })
  document.head.innerHTML =
    '<link rel="icon"><link rel="apple-touch-icon"><meta name="theme-color">'
})
describe('branding startup', () => {
  it('selects English and all TLF browser resources before rendering', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify({ profileId: 'tlf-prep-clubs', version: 2 })),
        ),
    )
    await bootstrapBranding('student', loaders)
    expect(bootstrapLocale).toHaveBeenCalledWith(loaders, 'en')
    expect(document.documentElement.dataset.brand).toBe('tlf-prep-clubs')
    expect(document.querySelector('link[rel="icon"]')?.getAttribute('href')).toBe(
      '/student/brands/tlf-prep-clubs/v1/icon.svg',
    )
    expect(document.querySelector('meta')?.content).toBe('#17384A')
  })
  it('uses the last validated selection offline', async () => {
    window.localStorage.setItem(
      'vmsh:branding:v1',
      JSON.stringify({ profileId: 'tlf-prep-clubs', version: 2 }),
    )
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))
    expect((await bootstrapBranding('family', loaders)).id).toBe('tlf-prep-clubs')
  })
  it('does not mask an unknown profile with an old cached profile', async () => {
    window.localStorage.setItem(
      'vmsh:branding:v1',
      JSON.stringify({ profileId: 'vmsh', version: 1 }),
    )
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ profileId: 'unknown', version: 3 }))),
    )
    await expect(bootstrapBranding('staff', loaders)).rejects.toThrow()
  })
  it('fails safely without a usable offline copy', async () => {
    window.localStorage.setItem('vmsh:branding:v1', '{')
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))
    await expect(bootstrapBranding('staff', loaders)).rejects.toThrow('offline')
  })
})

afterEach(() => vi.unstubAllGlobals())
