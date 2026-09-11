import { createRouter, RouterProvider } from '@tanstack/react-router'
import { StrictMode, useMemo } from 'react'
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
import {
  OfflineDatabaseProvider,
  createOfflineAuthenticationStore,
  useOfflineDatabase,
} from '@vmsh/offline'
import '@vmsh/ui/styles.css'
import '@vmsh/content/styles.css'
import './student-worksheet-print.css'

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

function studentApplication(runtime: RuntimeConfig) {
  const storageNamespace = createBrowserStorageNamespace(runtime)
  return (
    <AppProviders storageNamespace={storageNamespace}>
      <OfflineDatabaseProvider
        errorFallback={({ retry }) => (
          <AppStartupScreen
            description="Локальное хранилище сейчас недоступно. Отправка без сети не будет надёжной, поэтому кабинет не открыт."
            onRetry={retry}
            state="error"
            title="Не удалось подготовить работу без сети"
          />
        )}
        loadingFallback={
          <AppStartupScreen
            description="Проверяем сохранённые задания и черновики на этом устройстве."
            state="loading"
            title="Готовим работу без сети"
          />
        }
        runtime={{ audience: 'student', instance: runtime.instance }}
      >
        <StudentAuthenticatedApplication runtime={runtime} />
      </OfflineDatabaseProvider>
    </AppProviders>
  )
}

export function StudentAuthenticatedApplication({ runtime }: { runtime: RuntimeConfig }) {
  const database = useOfflineDatabase()
  const offlineStore = useMemo(
    () => createOfflineAuthenticationStore(database, 'student'),
    [database],
  )
  return (
    <AuthenticationProvider audience="student" offlineStore={offlineStore} runtime={runtime}>
      <RealtimeProvider audience="student" runtime={runtime}>
        <RouterProvider router={router} />
      </RealtimeProvider>
    </AuthenticationProvider>
  )
}

createRoot(rootElement).render(
  <StrictMode>
    {/* Update recovery must survive rejected runtime/IndexedDB bootstrap. */}
    <PwaUpdateController router={router} />
    {/* Phase 0: no protected Student route mounts before strict runtime validation. */}
    <RuntimeBootstrap audience="student">
      {(runtime) => studentApplication(runtime)}
    </RuntimeBootstrap>
  </StrictMode>,
)
