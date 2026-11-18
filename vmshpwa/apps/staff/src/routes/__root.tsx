import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { createRootRoute, Outlet, useRouterState } from '@tanstack/react-router'
import {
  BarChart3,
  ChartNoAxesCombined,
  Boxes,
  Building2,
  ClipboardCheck,
  House,
  LogOut,
  Mail,
  MessageCircleQuestion,
  MessageSquareWarning,
  Newspaper,
  ScrollText,
  Users,
  Palette,
  KeyRound,
  BookOpen,
  DoorOpen,
  FlaskConical,
  GraduationCap,
  Presentation,
  Video,
} from 'lucide-react'
import { useCallback, useState, type ReactNode } from 'react'

import {
  AppShell,
  InterfaceLanguageMenu,
  AuthenticationRedirectBoundary,
  StaffCapabilityBoundary,
  createRouterAuthReturnTo,
  isAuthenticationLoginPath,
  ProductPageView,
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
  /** BACKLOG Q10: nav groups only add headings and order; items are unchanged. */
  section: string
}

const navigation: StaffNavigationItem[] = [
  {
    get section() {
      return t`Работа`
    },
    get label() {
      return t`Сводка`
    },
    to: '/',
    icon: <House className="size-4" aria-hidden="true" />,
  },
  {
    get section() {
      return t`Работа`
    },
    get label() {
      return t`Проверка`
    },
    to: '/review',
    icon: <ClipboardCheck className="size-4" aria-hidden="true" />,
    capability: 'review.write',
  },
  {
    get section() {
      return t`Работа`
    },
    get label() {
      return t`Очное занятие`
    },
    to: '/in-person',
    icon: <Building2 className="size-4" aria-hidden="true" />,
    capability: 'oral.manage',
  },
  {
    get section() {
      return t`Работа`
    },
    get label() {
      return t`Zoom-приём`
    },
    to: '/oral',
    icon: <Video className="size-4" aria-hidden="true" />,
    capability: 'oral.manage',
  },
  {
    get section() {
      return t`Материалы`
    },
    get label() {
      return t`Уроки`
    },
    to: '/lessons',
    icon: <BookOpen className="size-4" aria-hidden="true" />,
  },
  {
    get section() {
      return t`Материалы`
    },
    get label() {
      return t`Материалы для разбора`
    },
    to: '/whiteboard-export',
    icon: <Presentation className="size-4" aria-hidden="true" />,
    capability: 'course.read',
  },
  {
    get section() {
      return t`Материалы`
    },
    get label() {
      return t`Курсы`
    },
    to: '/courses',
    icon: <Boxes className="size-4" aria-hidden="true" />,
  },
  {
    get section() {
      return t`Люди`
    },
    get label() {
      return t`Участники`
    },
    to: '/users',
    icon: <Users className="size-4" aria-hidden="true" />,
  },
  {
    get section() {
      return t`Люди`
    },
    get label() {
      return t`Результаты школьника`
    },
    to: '/student-results',
    icon: <GraduationCap className="size-4" aria-hidden="true" />,
    capability: 'audit.read',
  },
  {
    get section() {
      return t`Люди`
    },
    get label() {
      return t`Аудитории`
    },
    to: '/classrooms',
    icon: <DoorOpen className="size-4" aria-hidden="true" />,
    capability: 'classroom.manage',
  },
  {
    get section() {
      return t`Связь`
    },
    get label() {
      return t`Вопросы`
    },
    to: '/questions',
    icon: <MessageCircleQuestion className="size-4" aria-hidden="true" />,
  },
  {
    get section() {
      return t`Связь`
    },
    get label() {
      return t`Реакции`
    },
    to: '/reactions',
    icon: <MessageSquareWarning className="size-4" aria-hidden="true" />,
    capability: 'audit.read',
  },
  {
    get section() {
      return t`Связь`
    },
    get label() {
      return t`Новости`
    },
    to: '/news',
    icon: <Newspaper className="size-4" aria-hidden="true" />,
  },
  {
    get section() {
      return t`Связь`
    },
    get label() {
      return t`Рассылки`
    },
    to: '/broadcasts',
    icon: <Mail className="size-4" aria-hidden="true" />,
    capability: 'broadcast.manage',
  },
  {
    get section() {
      return t`Администрирование`
    },
    get label() {
      return t`Статистика`
    },
    to: '/statistics',
    icon: <BarChart3 className="size-4" aria-hidden="true" />,
  },
  {
    get section() {
      return t`Администрирование`
    },
    get label() {
      return t`Аналитика`
    },
    to: '/analytics',
    icon: <ChartNoAxesCombined className="size-4" aria-hidden="true" />,
    capability: 'product-analytics.read',
  },
  {
    get section() {
      return t`Администрирование`
    },
    get label() {
      return t`Аудит`
    },
    to: '/audit',
    icon: <ScrollText className="size-4" aria-hidden="true" />,
    capability: 'audit.read',
  },
  {
    get section() {
      return t`Администрирование`
    },
    get label() {
      return t`Оформление`
    },
    to: '/branding',
    icon: <Palette className="size-4" aria-hidden="true" />,
    capability: 'staff.manage',
  },
  {
    get section() {
      return t`Администрирование`
    },
    get label() {
      return t`Тестирование`
    },
    to: '/testing',
    icon: <FlaskConical className="size-4" aria-hidden="true" />,
    capability: 'content.manage',
  },
  {
    get section() {
      return t`Администрирование`
    },
    get label() {
      return t`MCP-доступ`
    },
    to: '/mcp-access',
    icon: <KeyRound className="size-4" aria-hidden="true" />,
    capability: 'review.write',
  },
]

export const Route = createRootRoute({
  component: StaffRootLayout,
  notFoundComponent: () => (
    <div className="p-8">
      <h1 className="text-xl font-semibold">
        <Trans>Страница не найдена</Trans>
      </h1>
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
      compactHeader={localPathname.startsWith('/in-person') || localPathname.startsWith('/oral')}
      title={t`Учитель и администратор`}
      displayName={principal.displayName}
      navigation={permittedNavigation}
      headerActions={
        <>
          <InterfaceLanguageMenu />
          <Button
            aria-label={t`Выйти из кабинета`}
            disabled={loggingOut}
            onClick={() => {
              setLoggingOut(true)
              void authentication.logout().finally(() => setLoggingOut(false))
            }}
            size="icon-sm"
            title={t`Выйти`}
            variant="ghost"
          >
            <LogOut aria-hidden="true" />
          </Button>
        </>
      }
    >
      <ProductPageView audience="staff" pathname={pathname} />
      <Outlet />
    </AppShell>
  )

  return requiredCapability ? (
    <StaffCapabilityBoundary capability={requiredCapability}>{shell}</StaffCapabilityBoundary>
  ) : (
    shell
  )
}
