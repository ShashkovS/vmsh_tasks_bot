import { i18n } from '@lingui/core'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { activateLocale, bootstrapLocale, currentLocale, type CatalogLoaders } from './activation'
import { LOCALE_COOKIE_NAME, writeLocaleCookie } from './locale-cookie'

// Catalog activation before the first render: see adr/0004-pwa-internationalization.md.
function loaders(overrides: Partial<CatalogLoaders> = {}): CatalogLoaders {
  return {
    ru: () => Promise.resolve({ messages: { 'test.activation': 'Проверка' } }),
    en: () => Promise.resolve({ messages: { 'test.activation': 'Check' } }),
    ...overrides,
  }
}

describe('catalog activation', () => {
  afterEach(() => {
    document.cookie = `${LOCALE_COOKIE_NAME}=; Path=/; Max-Age=0`
  })

  it('activates the device language and updates the document language', async () => {
    writeLocaleCookie('en')

    await expect(bootstrapLocale(loaders())).resolves.toBe('en')

    expect(currentLocale()).toBe('en')
    expect(document.documentElement.lang).toBe('en')
    expect(i18n._('test.activation')).toBe('Check')
  })

  it('uses Russian without a device choice', async () => {
    await expect(bootstrapLocale(loaders())).resolves.toBe('ru')
    expect(i18n._('test.activation')).toBe('Проверка')
  })

  it('falls back to Russian when the English catalog cannot load', async () => {
    writeLocaleCookie('en')
    const failingEnglish = vi.fn(() => Promise.reject(new TypeError('offline')))

    await expect(bootstrapLocale(loaders({ en: failingEnglish }))).resolves.toBe('ru')

    expect(failingEnglish).toHaveBeenCalledTimes(2)
    expect(currentLocale()).toBe('ru')
  })

  it('rejects when the Russian catalog cannot load after one retry', async () => {
    const failingRussian = vi.fn(() => Promise.reject(new TypeError('offline')))

    await expect(bootstrapLocale(loaders({ ru: failingRussian }))).rejects.toThrow('offline')
    expect(failingRussian).toHaveBeenCalledTimes(2)
  })

  it('retries a transient catalog failure once', async () => {
    const flaky = vi
      .fn<CatalogLoaders['en']>()
      .mockRejectedValueOnce(new TypeError('network'))
      .mockResolvedValueOnce({ messages: { 'test.activation': 'Check' } })

    await activateLocale('en', loaders({ en: flaky }))

    expect(flaky).toHaveBeenCalledTimes(2)
    expect(currentLocale()).toBe('en')
  })
})
