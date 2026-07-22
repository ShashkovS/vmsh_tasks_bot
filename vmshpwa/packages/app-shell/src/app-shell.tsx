import { Link } from '@tanstack/react-router'
import { Menu, Wifi } from 'lucide-react'
import type { ReactNode } from 'react'

import { Badge, Button } from '@vmsh/ui'

import { ThemeToggle } from './providers'

export interface NavigationItem {
  label: string
  to: string
  icon: ReactNode
}

export interface AppShellProps {
  product: 'student' | 'family' | 'staff'
  title: string
  navigation: NavigationItem[]
  children: ReactNode
  mobileNavigation?: boolean
}

export function AppShell({
  product,
  title,
  navigation,
  children,
  mobileNavigation = false,
}: AppShellProps) {
  return (
    <div className="min-h-svh bg-background text-foreground" data-product={product}>
      <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-[1600px] items-center gap-3 px-4">
          <div className="flex min-w-0 items-baseline gap-2">
            <Link className="truncate font-semibold tracking-tight" to="/">
              ВМШ 179
            </Link>
            <span className="hidden text-sm text-muted-foreground sm:inline">{title}</span>
          </div>
          <Badge className="hidden sm:inline-flex" variant="outline">
            Прототип
          </Badge>
          <div className="ml-auto flex items-center gap-1">
            <span className="hidden items-center gap-1 text-xs text-muted-foreground md:flex">
              <Wifi className="size-3.5" aria-hidden="true" /> синхронизировано
            </span>
            <ThemeToggle />
            <Button className="md:hidden" size="icon-sm" variant="ghost" aria-label="Открыть меню">
              <Menu aria-hidden="true" />
            </Button>
          </div>
        </div>
      </header>

      <div className="mx-auto flex max-w-[1600px]">
        {!mobileNavigation ? (
          <aside className="sticky top-14 hidden h-[calc(100svh-3.5rem)] w-56 shrink-0 border-r p-3 md:block">
            <nav aria-label="Основная навигация" className="space-y-1">
              {navigation.map((item) => (
                <Link
                  key={item.to}
                  activeProps={{ className: 'bg-accent text-accent-foreground' }}
                  className="flex min-h-9 items-center gap-2 rounded-md px-3 text-sm text-muted-foreground hover:bg-muted hover:text-foreground"
                  to={item.to}
                >
                  {item.icon}
                  <span>{item.label}</span>
                </Link>
              ))}
            </nav>
          </aside>
        ) : null}

        <main className={mobileNavigation ? 'w-full pb-20' : 'min-w-0 flex-1'}>{children}</main>
      </div>

      {mobileNavigation ? (
        <nav
          aria-label="Основная навигация"
          className="fixed inset-x-0 bottom-0 z-40 grid border-t bg-background/98 px-1 pb-[env(safe-area-inset-bottom)] md:hidden"
          style={{ gridTemplateColumns: `repeat(${navigation.length}, minmax(0, 1fr))` }}
        >
          {navigation.map((item) => (
            <Link
              key={item.to}
              activeProps={{ className: 'text-primary' }}
              className="flex min-h-16 flex-col items-center justify-center gap-1 px-1 text-[0.68rem] text-muted-foreground"
              to={item.to}
            >
              {item.icon}
              <span className="max-w-full truncate">{item.label}</span>
            </Link>
          ))}
        </nav>
      ) : null}
    </div>
  )
}
