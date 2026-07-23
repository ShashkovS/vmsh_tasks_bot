import { createRouter, RouterProvider } from '@tanstack/react-router'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { AppProviders, initFrontendObservability } from '@vmsh/app-shell'
import '@vmsh/ui/styles.css'

import { routeTree } from './routeTree.gen'
import { PwaUpdateController } from './pwa-update'

if (import.meta.env.PROD && import.meta.env.VITE_ENABLE_MSW === 'true') {
  throw new Error('MSW must never be enabled in a production build')
}

initFrontendObservability({
  audience: 'student',
  dsn: import.meta.env.VITE_SENTRY_DSN,
  enabled: import.meta.env.PROD,
  environment: import.meta.env.MODE,
  release: import.meta.env.VITE_SENTRY_RELEASE,
})

const router = createRouter({ routeTree, basepath: '/student', defaultPreload: 'intent' })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

const rootElement = document.getElementById('root')
if (!rootElement) throw new Error('Root element is missing')

createRoot(rootElement).render(
  <StrictMode>
    <AppProviders storageNamespace="student">
      <PwaUpdateController />
      <RouterProvider router={router} />
    </AppProviders>
  </StrictMode>,
)
