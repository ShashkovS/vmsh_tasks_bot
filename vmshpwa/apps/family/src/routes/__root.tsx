import { createRootRoute, Outlet, useRouterState } from '@tanstack/react-router'
import { House, Newspaper, UserRound, UsersRound } from 'lucide-react'
import { useCallback } from 'react'

import {
  AppShell,
  authenticationStatePrincipal,
  useAuthentication,
  AuthenticationRedirectBoundary,
  createRouterAuthReturnTo,
  isAuthenticationLoginPath,
  ProductPageView,
} from '@vmsh/app-shell'

const navigation = [
  { label: 'Сейчас', to: '/', icon: <House className="size-5" aria-hidden="true" /> },
  { label: 'Дети', to: '/children', icon: <UsersRound className="size-5" aria-hidden="true" /> },
  { label: 'Новости', to: '/news', icon: <Newspaper className="size-5" aria-hidden="true" /> },
  { label: 'Профиль', to: '/profile', icon: <UserRound className="size-5" aria-hidden="true" /> },
]

export const Route = createRootRoute({
  component: FamilyRootLayout,
  notFoundComponent: () => (
    <div className="p-8">
      <h1 className="text-xl font-semibold">Страница не найдена</h1>
    </div>
  ),
})

/* Login owns the separate shell required by design-system Phase 5. */
function FamilyRootLayout() {
  const location = useRouterState({ select: (state) => state.location })
  const pathname = location.pathname
  if (isAuthenticationLoginPath('family', pathname)) return <Outlet />

  return <FamilyProtectedShell location={location} />
}

function FamilyProtectedShell({
  location,
}: {
  location: { pathname: string; searchStr: string; hash: string }
}) {
  const navigate = Route.useNavigate()
  const principal = authenticationStatePrincipal(useAuthentication().state)
  const returnTo = createRouterAuthReturnTo('family', {
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
        product="family"
        title="Семья"
        displayName={principal?.displayName}
        navigation={navigation}
        mobileNavigation
      >
        <ProductPageView audience="family" pathname={location.pathname} />
        <Outlet />
      </AppShell>
    </AuthenticationRedirectBoundary>
  )
}
