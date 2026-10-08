import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { bootstrapBranding } from './index'
import type * as Contracts from '@vmsh/contracts'
import { bootstrapLocale } from '@vmsh/i18n'
import {
  createServiceTransport,
  pwaOfflineReadFetch,
  serviceAvailabilitySnapshot,
} from '@vmsh/contracts'
vi.mock('@vmsh/i18n', () => ({ bootstrapLocale: vi.fn().mockResolvedValue('en') }))
vi.mock('@vmsh/contracts', async (importOriginal) => ({
  ...(await importOriginal<typeof Contracts>()),
  serviceAvailabilitySnapshot: vi.fn(() => ({ state: 'ready', since: 0, prolonged: false })),
  pwaOfflineReadFetch: vi.fn((...args: Parameters<typeof fetch>) => fetch(...args)),
}))
const loaders = { ru: vi.fn(), en: vi.fn() }
beforeEach(() => {
  vi.restoreAllMocks()
  vi.mocked(serviceAvailabilitySnapshot).mockReturnValue({
    state: 'ready',
    since: 0,
    prolonged: false,
  })
  vi.mocked(pwaOfflineReadFetch).mockImplementation((...args) => fetch(...args))
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
  it('waits through a gateway failure instead of accepting an old cached identity', async () => {
    vi.useFakeTimers()
    window.localStorage.setItem(
      'vmsh:branding:v1',
      JSON.stringify({ profileId: 'vmsh', version: 1 }),
    )
    const fetchImplementation = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(new Response('Bad gateway', { status: 502 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ state: 'ready' })))
      .mockResolvedValueOnce(new Response('{}'))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ profileId: 'tlf-prep-clubs', version: 2 })),
      )
    const transport = createServiceTransport({
      fetch: fetchImplementation,
      origin: window.location.origin,
      random: () => 0,
    })
    vi.mocked(pwaOfflineReadFetch).mockImplementation(transport.fetchOfflineRead)
    const pending = bootstrapBranding('family', loaders)
    await vi.advanceTimersByTimeAsync(1000)
    expect((await pending).id).toBe('tlf-prep-clubs')
    expect(fetchImplementation).toHaveBeenCalledTimes(4)
    vi.useRealTimers()
  })
  it('shows an existing maintenance episode before the branding response arrives', async () => {
    vi.mocked(serviceAvailabilitySnapshot).mockReturnValue({
      state: 'updating',
      since: 1,
      prolonged: false,
    })
    let resolveResponse!: (response: Response) => void
    vi.stubGlobal(
      'fetch',
      vi.fn(
        () =>
          new Promise<Response>((resolve) => {
            resolveResponse = resolve
          }),
      ),
    )
    const root = document.createElement('div')
    const pending = bootstrapBranding('student', loaders, root)
    await vi.waitFor(() => expect(root.textContent).toContain('Обновляем сервис'))
    resolveResponse(new Response(JSON.stringify({ profileId: 'tlf-prep-clubs', version: 2 })))
    expect((await pending).id).toBe('tlf-prep-clubs')
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

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})
