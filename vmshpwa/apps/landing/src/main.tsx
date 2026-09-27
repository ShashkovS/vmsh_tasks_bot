import { t } from '@lingui/core/macro'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { LocaleProvider, bootstrapLocale, renderCatalogFailure } from '@vmsh/i18n'
import '@vmsh/ui/styles.css'

import { catalogLoaders } from './i18n/catalogs'
import { LandingPage } from './landing-page'

const rootElement = document.getElementById('root')
if (!rootElement) throw new Error('Root element is missing')

// The landing page follows the language last chosen on this device.
void bootstrapLocale(catalogLoaders).then(
  () => {
    document.title = t`ВМШ 179 — математический кружок`
    document
      .querySelector('meta[name="description"]')
      ?.setAttribute('content', t`ВМШ 179 — математический кружок для школьников и родителей`)
    createRoot(rootElement).render(
      <StrictMode>
        <LocaleProvider loaders={catalogLoaders}>
          <LandingPage />
        </LocaleProvider>
      </StrictMode>,
    )
  },
  () => renderCatalogFailure(rootElement),
)
