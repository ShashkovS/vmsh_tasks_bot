import { i18n, type Messages } from '@lingui/core'

import { DEFAULT_LOCALE, LOCALE_FORMATTING_TAGS, type Locale } from './locale'
import { readLocaleCookie } from './locale-cookie'

/** A compiled catalog module produced from `.po` files by `@lingui/vite-plugin`. */
export interface CatalogModule {
  messages: Messages
}

/**
 * Each application passes loaders for its own merged catalogs, so one chunk
 * per locale contains exactly the messages of that app and its packages.
 * See `apps/<app>/src/i18n/catalogs.ts`.
 */
export type CatalogLoaders = Readonly<Record<Locale, () => Promise<CatalogModule>>>

const loadedCatalogs = new Map<Locale, Messages>()

async function importCatalog(loader: () => Promise<CatalogModule>): Promise<CatalogModule> {
  try {
    return await loader()
  } catch {
    // One retry covers a transient network failure of the catalog chunk; the
    // PWAs precache it, so this path mostly matters for the Staff SPA.
    return await loader()
  }
}

export async function loadCatalog(locale: Locale, loaders: CatalogLoaders): Promise<void> {
  const { messages } = await importCatalog(loaders[locale])
  if (loadedCatalogs.get(locale) === messages) return
  i18n.load(locale, messages)
  loadedCatalogs.set(locale, messages)
}

/** Loads the catalog if needed and makes `locale` the active interface language. */
export async function activateLocale(locale: Locale, loaders: CatalogLoaders): Promise<void> {
  await loadCatalog(locale, loaders)
  if (i18n.locale !== locale) i18n.activate(locale, [LOCALE_FORMATTING_TAGS[locale]])
  if (typeof document !== 'undefined') document.documentElement.lang = locale
}

/**
 * Activates the device language (or Russian) before the first render. A
 * failed English catalog falls back to Russian; only a failed Russian catalog
 * rejects, and the caller shows the static reload screen.
 */
export async function bootstrapLocale(loaders: CatalogLoaders): Promise<Locale> {
  await enableDevelopmentCompiler()
  const preferred = readLocaleCookie() ?? DEFAULT_LOCALE
  try {
    await activateLocale(preferred, loaders)
    return preferred
  } catch (error) {
    if (preferred === DEFAULT_LOCALE) throw error
    await activateLocale(DEFAULT_LOCALE, loaders)
    return DEFAULT_LOCALE
  }
}

/**
 * Development only: messages added to code but not yet extracted still render
 * with their placeholders. Production builds drop this branch entirely and
 * rely on compiled catalogs (checked by the build guard in vite-i18n.ts).
 */
export async function enableDevelopmentCompiler(): Promise<void> {
  if (!import.meta.env.DEV) return
  const { compileMessage } = await import('@lingui/message-utils/compileMessage')
  i18n.setMessagesCompiler(compileMessage)
}

/** The active interface language for code outside React components. */
export function currentLocale(): Locale {
  return i18n.locale === 'en' ? 'en' : DEFAULT_LOCALE
}
