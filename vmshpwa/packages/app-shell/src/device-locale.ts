import type { InterfaceLocale } from '@vmsh/contracts'
import { DEFAULT_LOCALE, readLocaleCookie, writeLocaleCookie } from '@vmsh/i18n'

/**
 * Keeps the device cookie equal to the account language without switching the
 * current page: the next load uses it. Russian accounts on a fresh device keep
 * no cookie at all. See adr/0004-pwa-internationalization.md.
 */
export function syncDeviceLocale(locale: InterfaceLocale | undefined): void {
  if (!locale) return
  if ((readLocaleCookie() ?? DEFAULT_LOCALE) !== locale) writeLocaleCookie(locale)
}
