import { createRootRoute, Outlet, useRouterState } from '@tanstack/react-router'
import { BookOpenText, House, Newspaper, TrendingUp, UserRound } from 'lucide-react'

import { AppShell } from '@vmsh/app-shell'

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
  const pathname = useRouterState({ select: (state) => state.location.pathname })
  if (pathname.endsWith('/login')) return <Outlet />

  return (
    <AppShell product="student" title="Школьник" navigation={navigation} mobileNavigation>
      <Outlet />
    </AppShell>
  )
}
