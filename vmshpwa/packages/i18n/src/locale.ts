/**
 * Interface languages of the VMSH PWAs. Russian is the source language of all
 * product copy and the default for every account; English is a translation.
 * See `adr/0004-pwa-internationalization.md` and `docs/i18n.md`.
 */
export const SUPPORTED_LOCALES = ['ru', 'en'] as const
export type Locale = (typeof SUPPORTED_LOCALES)[number]
export const DEFAULT_LOCALE: Locale = 'ru'

/**
 * BCP 47 tags used for `Intl` formatting. English follows US conventions
 * (month first, 12-hour clock) by the owner's decision of 2026-09-19.
 */
export const LOCALE_FORMATTING_TAGS: Readonly<Record<Locale, string>> = {
  ru: 'ru-RU',
  en: 'en-US',
}

/**
 * Language names shown by the language selector. Each name is written in its
 * own language on purpose, so it is never passed through a translation.
 */
export const LOCALE_NATIVE_NAMES: Readonly<Record<Locale, string>> = {
  // eslint-disable-next-line lingui/no-unlocalized-strings -- a language's own name is never translated
  ru: 'Русский',
  en: 'English',
}

export function isLocale(value: unknown): value is Locale {
  return typeof value === 'string' && (SUPPORTED_LOCALES as readonly string[]).includes(value)
}
