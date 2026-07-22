import { createRootRoute, Outlet } from '@tanstack/react-router'
import { House, Newspaper, UserRound, UsersRound } from 'lucide-react'

import { AppShell } from '@vmsh/app-shell'

const navigation = [
  { label: 'Сейчас', to: '/', icon: <House className="size-5" aria-hidden="true" /> },
  { label: 'Дети', to: '/children', icon: <UsersRound className="size-5" aria-hidden="true" /> },
  { label: 'Новости', to: '/news', icon: <Newspaper className="size-5" aria-hidden="true" /> },
  { label: 'Профиль', to: '/profile', icon: <UserRound className="size-5" aria-hidden="true" /> },
]

export const Route = createRootRoute({
  component: () => (
    <AppShell product="family" title="Семья" navigation={navigation} mobileNavigation>
      <Outlet />
    </AppShell>
  ),
  notFoundComponent: () => (
    <div className="p-8">
      <h1 className="text-xl font-semibold">Страница не найдена</h1>
    </div>
  ),
})
