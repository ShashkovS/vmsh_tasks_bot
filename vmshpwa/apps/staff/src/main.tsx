import { createRouter, RouterProvider } from '@tanstack/react-router'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { AppProviders } from '@vmsh/app-shell'
import '@vmsh/ui/styles.css'

import { routeTree } from './routeTree.gen'

if (import.meta.env.PROD && import.meta.env.VITE_ENABLE_MSW === 'true') {
  throw new Error('MSW must never be enabled in a production build')
}

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
    <AppProviders storageNamespace="staff">
      <RouterProvider router={router} />
    </AppProviders>
  </StrictMode>,
)
