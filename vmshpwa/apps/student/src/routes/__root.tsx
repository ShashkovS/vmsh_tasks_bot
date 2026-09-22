import { currentLocale, dateTimeFormat } from '@vmsh/i18n'
import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
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
  PushOnboarding,
  useAuthentication,
} from '@vmsh/app-shell'
import { ConnectionBanner } from '@vmsh/product'

import { useStudentOfflineReadStatus } from '../offline-student-data'

const navigation = [
  {
    get label() {
      return t`Сейчас`
    },
    to: '/',
    icon: <House className="size-5" aria-hidden="true" />,
  },
  {
    get label() {
      return t`Задачи`
    },
    to: '/tasks',
    icon: <BookOpenText className="size-5" aria-hidden="true" />,
  },
  {
    get label() {
      return t`Новости`
    },
    to: '/news',
    icon: <Newspaper className="size-5" aria-hidden="true" />,
  },
  {
    get label() {
      return t`Прогресс`
    },
    to: '/progress',
    icon: <TrendingUp className="size-5" aria-hidden="true" />,
  },
  {
    get label() {
      return t`Профиль`
    },
    to: '/profile',
    icon: <UserRound className="size-5" aria-hidden="true" />,
  },
]

export const Route = createRootRoute({
  component: StudentRootLayout,
  notFoundComponent: () => (
    <div className="p-8">
      <h1 className="text-xl font-semibold">
        <Trans>Страница не найдена</Trans>
      </h1>
      <p className="mt-2 text-muted-foreground">
        <Trans>Проверьте адрес или вернитесь на текущую неделю.</Trans>
      </p>
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
        title={t`Школьник`}
        displayName={principal?.displayName}
        navigation={navigation}
        mobileNavigation
      >
        <ProductPageView audience="student" pathname={location.pathname} />
        {principal?.audience === 'student' && principal.isStaffTesting ? (
          <div
            role="status"
            className="mb-4 rounded-lg border border-border bg-muted p-3 text-small"
          >
            <Trans>
              Тестирование учителем. Отправки не входят в общую статистику.{' '}
              <a href="/staff/" className="underline">
                Вернуться в Staff
              </a>
            </Trans>
          </div>
        ) : null}
        <StudentOfflineSessionNotice />
        {!location.pathname.endsWith('/profile/notifications') ? <PushOnboarding /> : null}
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
    ? dateTimeFormat(currentLocale(), {
        dateStyle: 'medium',
        timeStyle: 'short',
      }).format(new Date(scopedOfflineRead.fetchedAt))
    : null
  return (
    <ConnectionBanner
      actionImpact={
        savedAt
          ? t`Показана последняя сохранённая копия от ${savedAt}.${scopedOfflineRead?.stale ? t` Срок свежести копии истёк.` : ''} Новые публикации и изменения появятся после восстановления связи.`
          : t`Показана последняя сохранённая копия. Новые публикации и изменения появятся после восстановления связи.`
      }
      className="mb-4"
      state="offline"
    />
  )
}
