import { t } from '@lingui/core/macro'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { LocaleProvider, renderCatalogFailure } from '@vmsh/i18n'
import { BrandIdentityProvider } from '@vmsh/ui'
import { brandAssetBase } from '@vmsh/contracts'
import { bootstrapBranding } from '@vmsh/branding'
import '@vmsh/ui/styles.css'

import { catalogLoaders } from './i18n/catalogs'
import { LandingPage } from './landing-page'

const rootElement = document.getElementById('root')
if (!rootElement) throw new Error('Root element is missing')

// The landing page follows the language last chosen on this device.
void bootstrapBranding('landing', catalogLoaders, rootElement).then(
  (profile) => {
    const brandName = profile.name
    document.title = t`${brandName} — математический кружок`
    document
      .querySelector('meta[name="description"]')
      ?.setAttribute('content', t`${brandName} — математический кружок для школьников и родителей`)
    createRoot(rootElement).render(
      <StrictMode>
        <BrandIdentityProvider
          identity={{
            name: profile.name,
            supportEmail: profile.supportEmail,
            logoUrl:
              profile.id === 'vmsh' ? undefined : `${brandAssetBase(profile, 'landing')}icon.svg`,
          }}
        >
          <LocaleProvider loaders={catalogLoaders}>
            <LandingPage />
          </LocaleProvider>
        </BrandIdentityProvider>
      </StrictMode>,
    )
  },
  () => renderCatalogFailure(rootElement),
)
