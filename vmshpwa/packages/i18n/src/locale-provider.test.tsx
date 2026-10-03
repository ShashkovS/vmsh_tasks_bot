import { useLingui } from '@lingui/react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { bootstrapLocale, type CatalogLoaders } from './activation'
import { LOCALE_COOKIE_NAME, readLocaleCookie } from './locale-cookie'
import { LocaleProvider, useLocale } from './locale-provider'

// Live language switch without reload: see adr/0004-pwa-internationalization.md.
const loaders: CatalogLoaders = {
  ru: () => Promise.resolve({ messages: { 'test.provider': 'Привет' } }),
  en: () => Promise.resolve({ messages: { 'test.provider': 'Hello' } }),
}

function Greeting() {
  const { i18n } = useLingui()
  const { locale, changeLocale } = useLocale()
  return (
    <button data-locale={locale} onClick={() => void changeLocale('en')} type="button">
      {i18n._('test.provider')}
    </button>
  )
}

describe('LocaleProvider', () => {
  afterEach(() => {
    cleanup()
    document.cookie = `${LOCALE_COOKIE_NAME}=; Path=/; Max-Age=0`
  })

  it('re-renders translated text, the document language and the device cookie', async () => {
    await bootstrapLocale(loaders)
    render(
      <LocaleProvider loaders={loaders}>
        <Greeting />
      </LocaleProvider>,
    )
    const russian = screen.getByRole('button', { name: 'Привет' })
    expect(russian.dataset.locale).toBe('ru')

    fireEvent.click(russian)

    const english = await screen.findByRole('button', { name: 'Hello' })
    expect(english.dataset.locale).toBe('en')
    expect(document.documentElement.lang).toBe('en')
    expect(readLocaleCookie()).toBe('en')
  })

  it('requires the provider', () => {
    expect(() => render(<Greeting />)).toThrow()
  })
})
