import { createRootRoute, Outlet, useRouterState } from '@tanstack/react-router'
import { BookOpenText, House, Newspaper, TrendingUp, UserRound } from 'lucide-react'
import { useCallback } from 'react'

import {
  AppShell,
  authenticationStatePrincipal,
  AuthenticationRedirectBoundary,
  createRouterAuthReturnTo,
  isAuthenticationLoginPath,
  ProductPageView,
  useAuthentication,
} from '@vmsh/app-shell'
import { ConnectionBanner } from '@vmsh/product'

import { useStudentOfflineReadStatus } from '../offline-student-data'

const navigation = [
  { label: 'Сейчас', to: '/', icon: <House className="size-5" aria-hidden="true" /> },
  { label: 'Задачи', to: '/tasks', icon: <BookOpenText className="size-5" aria-hidden="true" /> },
  { label: 'Новости', to: '/news', icon: <Newspaper className="size-5" aria-hidden="true" /> },
  {
    label: 'Прогресс',
    to: '/progress',
    icon: <TrendingUp className="size-5" aria-hidden="true" />,
  },
  { label: 'Профиль', to: '/profile', icon: <UserRound className="size-5" aria-hidden="true" /> },
]

export const Route = createRootRoute({
  component: StudentRootLayout,
  notFoundComponent: () => (
    <div className="p-8">
      <h1 className="text-xl font-semibold">Страница не найдена</h1>
      <p className="mt-2 text-muted-foreground">Проверьте адрес или вернитесь на текущую неделю.</p>
    </div>
  ),
})

/* Login owns the separate, distraction-free shell required by Phase 5. */
function StudentRootLayout() {
  const location = useRouterState({ select: (state) => state.location })
  const pathname = location.pathname
  if (isAuthenticationLoginPath('student', pathname)) return <Outlet />

  return <StudentProtectedShell location={location} />
}

function StudentProtectedShell({
  location,
}: {
  location: { pathname: string; searchStr: string; hash: string }
}) {
  const navigate = Route.useNavigate()
  const principal = authenticationStatePrincipal(useAuthentication().state)
  const returnTo = createRouterAuthReturnTo('student', {
    pathname: location.pathname,
    search: location.searchStr,
    hash: location.hash ? `#${location.hash}` : '',
  })
  const redirectToLogin = useCallback(() => {
    void navigate({ to: '/login', search: { returnTo }, replace: true })
  }, [navigate, returnTo])

  return (
    <AuthenticationRedirectBoundary onAuthenticationRequired={redirectToLogin}>
      <AppShell
        compactHeader={location.pathname.startsWith('/tasks')}
        product="student"
        title="Школьник"
        displayName={principal?.displayName}
        navigation={navigation}
        mobileNavigation
      >
        <ProductPageView audience="student" pathname={location.pathname} />
        <StudentOfflineSessionNotice />
        <Outlet />
      </AppShell>
    </AuthenticationRedirectBoundary>
  )
}

function StudentOfflineSessionNotice() {
  const authentication = useAuthentication()
  const offlineRead = useStudentOfflineReadStatus()
  const principal =
    authentication.state.status === 'authenticated' ||
    authentication.state.status === 'offline-unverified'
      ? authentication.state.principal
      : null
  const scopedOfflineRead =
    principal && offlineRead?.ownerId === principal.accountId ? offlineRead : null
  if (authentication.state.status !== 'offline-unverified' && scopedOfflineRead === null)
    return null
  const savedAt = scopedOfflineRead
    ? new Intl.DateTimeFormat('ru-RU', {
        dateStyle: 'medium',
        timeStyle: 'short',
      }).format(new Date(scopedOfflineRead.fetchedAt))
    : null
  return (
    <ConnectionBanner
      actionImpact={
        savedAt
          ? `Показана последняя сохранённая копия от ${savedAt}.${scopedOfflineRead?.stale ? ' Срок свежести копии истёк.' : ''} Новые публикации и изменения появятся после восстановления связи.`
          : 'Показана последняя сохранённая копия. Новые публикации и изменения появятся после восстановления связи.'
      }
      className="mb-4"
      state="offline"
    />
  )
}
