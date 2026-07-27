import { createRouter, RouterProvider } from '@tanstack/react-router'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { AppProviders, RuntimeBootstrap, initFrontendObservability } from '@vmsh/app-shell'
import { createBrowserStorageNamespace } from '@vmsh/contracts'
import '@vmsh/ui/styles.css'

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

createRoot(rootElement).render(
  <StrictMode>
    {/* Staff validates its runtime too, but deliberately has no Dexie/offline database. */}
    <RuntimeBootstrap audience="staff">
      {(runtime) => (
        <AppProviders storageNamespace={createBrowserStorageNamespace(runtime)}>
          <RouterProvider router={router} />
        </AppProviders>
      )}
    </RuntimeBootstrap>
  </StrictMode>,
)
