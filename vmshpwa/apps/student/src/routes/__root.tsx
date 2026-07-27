import { createRootRoute, Outlet, useRouterState } from '@tanstack/react-router'
import { BookOpenText, House, Newspaper, TrendingUp, UserRound } from 'lucide-react'
import { useCallback } from 'react'

import {
  AppShell,
  AuthenticationRedirectBoundary,
  createRouterAuthReturnTo,
  isAuthenticationLoginPath,
} from '@vmsh/app-shell'

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
      <AppShell product="student" title="Школьник" navigation={navigation} mobileNavigation>
        <Outlet />
      </AppShell>
    </AuthenticationRedirectBoundary>
  )
}
