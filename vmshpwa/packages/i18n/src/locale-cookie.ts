import { isLocale, type Locale } from './locale'

/**
 * Device-level interface language. The account preference (`principal.locale`)
 * stays authoritative after sign-in; this cookie only lets screens before
 * sign-in and the backend (HTTP and WebSocket handshakes) use the language
 * the person last chose on this device. It is not user data and is shared
 * by all three audiences of one origin. See `docs/i18n.md`.
 */
export const LOCALE_COOKIE_NAME = 'vmsh-locale'
const LOCALE_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 365

export function parseLocaleCookie(cookieHeader: string): Locale | null {
  for (const part of cookieHeader.split(';')) {
    const separator = part.indexOf('=')
    if (separator < 0) continue
    if (part.slice(0, separator).trim() !== LOCALE_COOKIE_NAME) continue
    const value = part.slice(separator + 1).trim()
    return isLocale(value) ? value : null
  }
  return null
}

export function readLocaleCookie(): Locale | null {
  try {
    return typeof document === 'undefined' ? null : parseLocaleCookie(document.cookie)
  } catch {
    // Cookie access can be denied in sandboxed contexts; the default language
    // is always a safe fallback for a cosmetic preference.
    return null
  }
}

export function writeLocaleCookie(locale: Locale): void {
  try {
    const secure = window.location.protocol === 'https:' ? '; Secure' : ''
    document.cookie = `${LOCALE_COOKIE_NAME}=${locale}; Path=/; Max-Age=${LOCALE_COOKIE_MAX_AGE_SECONDS}; SameSite=Lax${secure}`
  } catch {
    // Keep the in-memory language for this page when cookies are denied.
  }
}
