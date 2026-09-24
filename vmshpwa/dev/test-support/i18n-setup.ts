import { afterEach } from 'vitest'

import { i18n } from '@lingui/core'
import { compileMessage } from '@lingui/message-utils/compileMessage'

import { DEFAULT_LOCALE, activateLocale, loadCatalog } from '@vmsh/i18n'

import { allCatalogLoaders } from './i18n-catalogs'

// Unit tests render in Russian, the source language, so existing assertions on
// Russian copy stay valid. English is preloaded for tests that switch locale.
// Messages added before `make pwa-i18n-extract` still render with placeholders.
i18n.setMessagesCompiler(compileMessage)
await activateLocale(DEFAULT_LOCALE, allCatalogLoaders)
await loadCatalog('en', allCatalogLoaders)

afterEach(async () => {
  await activateLocale(DEFAULT_LOCALE, allCatalogLoaders)
})
