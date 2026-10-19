import { afterEach, describe, expect, it } from 'vitest'

import {
  LOCALE_COOKIE_NAME,
  parseLocaleCookie,
  readLocaleCookie,
  writeLocaleCookie,
} from './locale-cookie'

// Device language cookie: see docs/i18n.md and docs/runtime-isolation.md.
describe('locale cookie', () => {
  afterEach(() => {
    document.cookie = `${LOCALE_COOKIE_NAME}=; Path=/; Max-Age=0`
  })

  it('parses only supported values of its own cookie', () => {
    expect(parseLocaleCookie('a=1; vmsh-locale=en; b=2')).toBe('en')
    expect(parseLocaleCookie('vmsh-locale=ru')).toBe('ru')
    expect(parseLocaleCookie('vmsh-locale=EN')).toBeNull()
    expect(parseLocaleCookie('vmsh-locale=de')).toBeNull()
    expect(parseLocaleCookie('other-vmsh-locale=en')).toBeNull()
    expect(parseLocaleCookie('')).toBeNull()
  })

  it('round-trips the chosen language through document.cookie', () => {
    expect(readLocaleCookie()).toBeNull()
    writeLocaleCookie('en')
    expect(readLocaleCookie()).toBe('en')
    writeLocaleCookie('ru')
    expect(readLocaleCookie()).toBe('ru')
  })
})
