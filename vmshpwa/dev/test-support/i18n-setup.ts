import { afterEach } from 'vitest'

import { DEFAULT_LOCALE, activateLocale, loadCatalog } from '@vmsh/i18n'

import { allCatalogLoaders } from './i18n-catalogs'

// Unit tests render in Russian, the source language, so existing assertions on
// Russian copy stay valid. English is preloaded for tests that switch locale.
await activateLocale(DEFAULT_LOCALE, allCatalogLoaders)
await loadCatalog('en', allCatalogLoaders)

afterEach(async () => {
  await activateLocale(DEFAULT_LOCALE, allCatalogLoaders)
})
