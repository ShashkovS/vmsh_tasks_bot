import { createRootRoute, Outlet, useRouterState } from '@tanstack/react-router'
import {
  BarChart3,
  BookOpenCheck,
  Boxes,
  Building2,
  ClipboardCheck,
  FileText,
  House,
  Mail,
  MessageCircleQuestion,
  Mic2,
  Newspaper,
  ScrollText,
  Users,
} from 'lucide-react'

import { AppShell } from '@vmsh/app-shell'

const navigation = [
  { label: 'Сводка', to: '/', icon: <House className="size-4" aria-hidden="true" /> },
  {
    label: 'Проверка',
    to: '/review',
    icon: <ClipboardCheck className="size-4" aria-hidden="true" />,
  },
  {
    label: 'Вопросы',
    to: '/questions',
    icon: <MessageCircleQuestion className="size-4" aria-hidden="true" />,
  },
  { label: 'Устные', to: '/oral', icon: <Mic2 className="size-4" aria-hidden="true" /> },
  { label: 'Уроки', to: '/lessons', icon: <BookOpenCheck className="size-4" aria-hidden="true" /> },
  { label: 'Курсы', to: '/courses', icon: <Boxes className="size-4" aria-hidden="true" /> },
  { label: 'Задачи', to: '/problems', icon: <FileText className="size-4" aria-hidden="true" /> },
  { label: 'Новости', to: '/news', icon: <Newspaper className="size-4" aria-hidden="true" /> },
  { label: 'Участники', to: '/users', icon: <Users className="size-4" aria-hidden="true" /> },
  {
    label: 'Аудитории',
    to: '/classrooms',
    icon: <Building2 className="size-4" aria-hidden="true" />,
  },
  { label: 'Рассылки', to: '/broadcasts', icon: <Mail className="size-4" aria-hidden="true" /> },
  {
    label: 'Статистика',
    to: '/statistics',
    icon: <BarChart3 className="size-4" aria-hidden="true" />,
  },
  { label: 'Аудит', to: '/audit', icon: <ScrollText className="size-4" aria-hidden="true" /> },
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
  const pathname = useRouterState({ select: (state) => state.location.pathname })
  if (pathname.endsWith('/login')) return <Outlet />

  return (
    <AppShell product="staff" title="Учитель и администратор" navigation={navigation}>
      <Outlet />
    </AppShell>
  )
}
