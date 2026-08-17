import { createRootRoute, Outlet, useRouterState } from '@tanstack/react-router'
import {
  BarChart3,
  BookOpenCheck,
  Boxes,
  Building2,
  ClipboardCheck,
  House,
  LogOut,
  Mail,
  MessageCircleQuestion,
  MessageSquareWarning,
  Mic2,
  Newspaper,
  ScrollText,
  Users,
} from 'lucide-react'
import { useCallback, useState, type ReactNode } from 'react'

import {
  AppShell,
  AuthenticationRedirectBoundary,
  StaffCapabilityBoundary,
  createRouterAuthReturnTo,
  isAuthenticationLoginPath,
  useAuthenticatedPrincipal,
  useAuthentication,
} from '@vmsh/app-shell'
import { Button } from '@vmsh/ui'
import type { StaffCapability } from '@vmsh/contracts'

interface StaffNavigationItem {
  label: string
  to: string
  icon: ReactNode
  capability?: StaffCapability
}

const navigation: StaffNavigationItem[] = [
  { label: 'Сводка', to: '/', icon: <House className="size-4" aria-hidden="true" /> },
  {
    label: 'Проверка',
    to: '/review',
    icon: <ClipboardCheck className="size-4" aria-hidden="true" />,
    capability: 'review.write',
  },
  {
    label: 'Реакции',
    to: '/reactions',
    icon: <MessageSquareWarning className="size-4" aria-hidden="true" />,
    capability: 'audit.read',
  },
  {
    label: 'Вопросы',
    to: '/questions',
    icon: <MessageCircleQuestion className="size-4" aria-hidden="true" />,
  },
  { label: 'Устные', to: '/oral', icon: <Mic2 className="size-4" aria-hidden="true" /> },
  { label: 'Уроки', to: '/lessons', icon: <BookOpenCheck className="size-4" aria-hidden="true" /> },
  { label: 'Курсы', to: '/courses', icon: <Boxes className="size-4" aria-hidden="true" /> },
  { label: 'Новости', to: '/news', icon: <Newspaper className="size-4" aria-hidden="true" /> },
  { label: 'Участники', to: '/users', icon: <Users className="size-4" aria-hidden="true" /> },
  {
    label: 'Аудитории',
    to: '/classrooms',
    icon: <Building2 className="size-4" aria-hidden="true" />,
    capability: 'classroom.manage',
  },
  {
    label: 'Рассылки',
    to: '/broadcasts',
    icon: <Mail className="size-4" aria-hidden="true" />,
    capability: 'broadcast.manage',
  },
  {
    label: 'Статистика',
    to: '/statistics',
    icon: <BarChart3 className="size-4" aria-hidden="true" />,
  },
  {
    label: 'Аудит',
    to: '/audit',
    icon: <ScrollText className="size-4" aria-hidden="true" />,
    capability: 'audit.read',
  },
]

export const Route = createRootRoute({
  component: StaffRootLayout,
  notFoundComponent: () => (
    <div className="p-8">
      <h1 className="text-xl font-semibold">Страница не найдена</h1>
    </div>
  ),
})

/* Login owns the separate shell required by design-system Phase 5. */
function StaffRootLayout() {
  const location = useRouterState({ select: (state) => state.location })
  const pathname = location.pathname
  if (isAuthenticationLoginPath('staff', pathname)) return <Outlet />

  return <StaffProtectedShell location={location} />
}

function StaffProtectedShell({
  location,
}: {
  location: { pathname: string; searchStr: string; hash: string }
}) {
  const navigate = Route.useNavigate()
  const returnTo = createRouterAuthReturnTo('staff', {
    pathname: location.pathname,
    search: location.searchStr,
    hash: location.hash ? `#${location.hash}` : '',
  })
  const redirectToLogin = useCallback(() => {
    void navigate({ to: '/login', search: { returnTo }, replace: true })
  }, [navigate, returnTo])

  return (
    <AuthenticationRedirectBoundary onAuthenticationRequired={redirectToLogin}>
      <AuthenticatedStaffShell pathname={location.pathname} />
    </AuthenticationRedirectBoundary>
  )
}

function AuthenticatedStaffShell({ pathname }: { pathname: string }) {
  const principal = useAuthenticatedPrincipal()
  const authentication = useAuthentication()
  const [loggingOut, setLoggingOut] = useState(false)
  if (principal.audience !== 'staff') return null
  const localPathname = createRouterAuthReturnTo('staff', { pathname })
  const permittedNavigation = navigation.filter(
    (item) => !item.capability || principal.capabilities.includes(item.capability),
  )
  const requiredCapability = navigation.find(
    (item) =>
      item.capability && (localPathname === item.to || localPathname.startsWith(`${item.to}/`)),
  )?.capability
  const shell = (
    <AppShell
      product="staff"
      title="Учитель и администратор"
      navigation={permittedNavigation}
      headerActions={
        <Button
          aria-label="Выйти из кабинета"
          disabled={loggingOut}
          onClick={() => {
            setLoggingOut(true)
            void authentication.logout().finally(() => setLoggingOut(false))
          }}
          size="icon-sm"
          title="Выйти"
          variant="ghost"
        >
          <LogOut aria-hidden="true" />
        </Button>
      }
    >
      <Outlet />
    </AppShell>
  )

  return requiredCapability ? (
    <StaffCapabilityBoundary capability={requiredCapability}>{shell}</StaffCapabilityBoundary>
  ) : (
    shell
  )
}
