import { Link } from '@tanstack/react-router'
import { Menu, Wifi } from 'lucide-react'
import { useState, type ReactNode } from 'react'

import {
  Button,
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
} from '@vmsh/ui'

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
  headerActions?: ReactNode
}

export function AppShell({
  product,
  title,
  navigation,
  children,
  mobileNavigation = false,
  headerActions,
}: AppShellProps) {
  const [menuOpen, setMenuOpen] = useState(false)

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
          <div className="ml-auto flex items-center gap-1">
            <span className="hidden items-center gap-1 text-xs text-muted-foreground md:flex">
              <Wifi className="size-3.5" aria-hidden="true" /> синхронизировано
            </span>
            <ThemeToggle />
            {headerActions}
            {!mobileNavigation ? (
              <Button
                className="md:hidden"
                onClick={() => setMenuOpen(true)}
                size="icon-sm"
                variant="ghost"
                aria-label="Открыть меню"
              >
                <Menu aria-hidden="true" />
              </Button>
            ) : null}
          </div>
        </div>
      </header>

      <div className="mx-auto flex max-w-[1600px]">
        <aside className="sticky top-14 hidden h-[calc(100svh-3.5rem)] w-56 shrink-0 border-r p-3 md:block">
          <ShellNavigation navigation={navigation} />
        </aside>

        <main className={mobileNavigation ? 'min-w-0 flex-1 pb-20 md:pb-0' : 'min-w-0 flex-1'}>
          {children}
        </main>
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

      {!mobileNavigation ? (
        <Drawer onOpenChange={setMenuOpen} open={menuOpen} side="left">
          <DrawerContent>
            <DrawerHeader>
              <DrawerTitle>ВМШ 179 · {title}</DrawerTitle>
              <DrawerDescription>Разделы рабочего кабинета</DrawerDescription>
            </DrawerHeader>
            <div className="min-h-0 flex-1 overflow-y-auto p-3 pt-0">
              <ShellNavigation navigation={navigation} onNavigate={() => setMenuOpen(false)} />
            </div>
          </DrawerContent>
        </Drawer>
      ) : null}
    </div>
  )
}

/* Navigation behavior is specified in dev/design-system/05-pages-and-flows.md;
 * apps/{student,family,staff}/src/routes/__root.tsx own the audience lists. */
function ShellNavigation({
  navigation,
  onNavigate,
}: {
  navigation: NavigationItem[]
  onNavigate?: () => void
}) {
  return (
    <nav aria-label="Основная навигация" className="space-y-1">
      {navigation.map((item) => (
        <Link
          activeProps={{ className: 'bg-accent text-accent-foreground' }}
          className="flex min-h-9 items-center gap-2 rounded-md px-3 text-sm text-muted-foreground hover:bg-muted hover:text-foreground"
          key={item.to}
          onClick={onNavigate}
          to={item.to}
        >
          {item.icon}
          <span>{item.label}</span>
        </Link>
      ))}
    </nav>
  )
}
