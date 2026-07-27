import { createRouter, RouterProvider } from '@tanstack/react-router'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import {
  AppProviders,
  AppStartupScreen,
  AuthenticationProvider,
  RealtimeProvider,
  RuntimeBootstrap,
  initFrontendObservability,
} from '@vmsh/app-shell'
import { createBrowserStorageNamespace, type RuntimeConfig } from '@vmsh/contracts'
import { OfflineDatabaseProvider } from '@vmsh/offline'
import '@vmsh/ui/styles.css'

import { routeTree } from './routeTree.gen'
import { PwaUpdateController } from './pwa-update'

if (import.meta.env.PROD && import.meta.env.VITE_ENABLE_MSW === 'true') {
  throw new Error('MSW must never be enabled in a production build')
}

initFrontendObservability({
  audience: 'family',
  dsn: import.meta.env.VITE_SENTRY_DSN,
  enabled: import.meta.env.PROD,
  environment: import.meta.env.MODE,
  release: import.meta.env.VITE_SENTRY_RELEASE,
})

const router = createRouter({ routeTree, basepath: '/family', defaultPreload: 'intent' })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

const rootElement = document.getElementById('root')
if (!rootElement) throw new Error('Root element is missing')

function familyApplication(runtime: RuntimeConfig) {
  const storageNamespace = createBrowserStorageNamespace(runtime)
  return (
    <AppProviders storageNamespace={storageNamespace}>
      <OfflineDatabaseProvider
        errorFallback={({ retry }) => (
          <AppStartupScreen
            description="Локальное хранилище сейчас недоступно. Чтобы не потерять сохранённые материалы, кабинет не открыт."
            onRetry={retry}
            state="error"
            title="Не удалось подготовить работу без сети"
          />
        )}
        loadingFallback={
          <AppStartupScreen
            description="Проверяем сохранённые материалы на этом устройстве."
            state="loading"
            title="Готовим работу без сети"
          />
        }
        runtime={{ audience: 'family', instance: runtime.instance }}
      >
        <AuthenticationProvider audience="family" runtime={runtime}>
          <RealtimeProvider audience="family" runtime={runtime}>
            <RouterProvider router={router} />
          </RealtimeProvider>
        </AuthenticationProvider>
      </OfflineDatabaseProvider>
    </AppProviders>
  )
}

createRoot(rootElement).render(
  <StrictMode>
    {/* Update recovery must survive rejected runtime/IndexedDB bootstrap. */}
    <PwaUpdateController />
    {/* Phase 0: no protected Family route mounts before strict runtime validation. */}
    <RuntimeBootstrap audience="family">{(runtime) => familyApplication(runtime)}</RuntimeBootstrap>
  </StrictMode>,
)
