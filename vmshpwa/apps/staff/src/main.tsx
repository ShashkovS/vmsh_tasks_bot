import { createRouter, RouterProvider } from '@tanstack/react-router'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import {
  AppProviders,
  AuthenticationProvider,
  RealtimeProvider,
  RuntimeBootstrap,
  initFrontendObservability,
} from '@vmsh/app-shell'
import { createBrowserStorageNamespace } from '@vmsh/contracts'
import { LocaleProvider, bootstrapLocale, renderCatalogFailure } from '@vmsh/i18n'
import '@vmsh/ui/styles.css'

import { catalogLoaders } from './i18n/catalogs'
import { routeTree } from './routeTree.gen'

if (import.meta.env.PROD && import.meta.env.VITE_ENABLE_MSW === 'true') {
  throw new Error('MSW must never be enabled in a production build')
}

initFrontendObservability({
  audience: 'staff',
  dsn: import.meta.env.VITE_SENTRY_DSN,
  enabled: import.meta.env.PROD,
  environment: import.meta.env.MODE,
  release: import.meta.env.VITE_SENTRY_RELEASE,
})

const router = createRouter({ routeTree, basepath: '/staff', defaultPreload: 'intent' })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

const rootElement = document.getElementById('root')
if (!rootElement) throw new Error('Root element is missing')

// The catalog is activated before the first render, so the runtime startup
// screen is translated too. See `docs/i18n.md`.
void bootstrapLocale(catalogLoaders).then(
  () => {
    createRoot(rootElement).render(
      <StrictMode>
        <LocaleProvider loaders={catalogLoaders}>
          {/* Staff validates its runtime too, but deliberately has no Dexie/offline database. */}
          <RuntimeBootstrap audience="staff">
            {(runtime) => (
              <AppProviders storageNamespace={createBrowserStorageNamespace(runtime)}>
                <AuthenticationProvider audience="staff" runtime={runtime}>
                  <RealtimeProvider audience="staff" runtime={runtime}>
                    <RouterProvider router={router} />
                  </RealtimeProvider>
                </AuthenticationProvider>
              </AppProviders>
            )}
          </RuntimeBootstrap>
        </LocaleProvider>
      </StrictMode>,
    )
  },
  () => renderCatalogFailure(rootElement),
)
