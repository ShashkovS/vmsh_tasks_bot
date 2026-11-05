import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { Link } from '@tanstack/react-router'
import { Menu } from 'lucide-react'
import { Fragment, useEffect, useState, type ReactNode } from 'react'

import {
  Button,
  Sign179,
  useBrandIdentity,
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
  /** Optional group heading; consecutive items with the same section share it. */
  section?: string
}

export interface AppShellProps {
  product: 'student' | 'family' | 'staff'
  title: string
  displayName?: string | undefined
  navigation: NavigationItem[]
  children: ReactNode
  mobileNavigation?: boolean
  headerActions?: ReactNode
  compactHeader?: boolean
}

export function AppShell({
  product,
  title,
  displayName,
  navigation,
  children,
  mobileNavigation = false,
  headerActions,
  compactHeader = false,
}: AppShellProps) {
  const brand = useBrandIdentity()
  const [menuOpen, setMenuOpen] = useState(false)
  // The fixed bottom navigation must not hide whatever the browser scrolls into view
  // (e.g. a focused answer field and its send button), dev/ui-audit-20261104/BACKLOG.md 1B.16.
  useEffect(() => {
    if (!mobileNavigation) return
    const root = document.documentElement
    const previous = root.style.scrollPaddingBottom
    root.style.scrollPaddingBottom = 'calc(5.5rem + env(safe-area-inset-bottom))'
    return () => {
      root.style.scrollPaddingBottom = previous
    }
  }, [mobileNavigation])

  return (
    <div className="min-h-svh bg-background text-foreground" data-product={product}>
      <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur">
        <div
          className={`mx-auto flex max-w-[1600px] items-center gap-3 px-4 ${compactHeader ? 'h-10' : 'h-14'}`}
        >
          <div className="flex min-w-0 items-center gap-2">
            <Link className="shrink-0 font-semibold tracking-tight" to="/">
              <span className="inline-flex items-center gap-2">
                <Sign179 size={24} />
                <span>{brand.name}</span>
              </span>
            </Link>
            {displayName || !compactHeader ? (
              <span
                className={
                  displayName
                    ? 'truncate border-l border-border pl-2 text-sm leading-5 text-muted-foreground'
                    : 'hidden border-l border-border pl-2 text-sm leading-5 text-muted-foreground sm:inline'
                }
                title={displayName ?? title}
              >
                {displayName ?? title}
              </span>
            ) : null}
          </div>
          <div className="ml-auto flex shrink-0 items-center gap-1">
            <ThemeToggle />
            {headerActions}
            {!mobileNavigation ? (
              <Button
                className="md:hidden"
                onClick={() => setMenuOpen(true)}
                size="icon-sm"
                variant="ghost"
                aria-label={t`Открыть меню`}
              >
                <Menu aria-hidden="true" />
              </Button>
            ) : null}
          </div>
        </div>
      </header>

      <div className="mx-auto flex max-w-[1600px]">
        <aside
          className={`sticky hidden w-60 shrink-0 overflow-y-auto overscroll-contain border-r p-3 md:block ${
            compactHeader ? 'top-10 h-[calc(100svh-2.5rem)]' : 'top-14 h-[calc(100svh-3.5rem)]'
          }`}
        >
          <ShellNavigation navigation={navigation} />
        </aside>

        <main className={mobileNavigation ? 'min-w-0 flex-1 pb-20 md:pb-0' : 'min-w-0 flex-1'}>
          {children}
        </main>
      </div>

      {mobileNavigation ? (
        <nav
          aria-label={t`Основная навигация`}
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
              <DrawerTitle>
                {brand.name} · {displayName ?? title}
              </DrawerTitle>
              <DrawerDescription>
                <Trans>Разделы рабочего кабинета</Trans>
              </DrawerDescription>
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
    <nav aria-label={t`Основная навигация`} className="space-y-1">
      {navigation.map((item, index) => (
        <Fragment key={item.to}>
          {item.section && item.section !== navigation[index - 1]?.section ? (
            <p
              className={`px-3 pb-1 text-caption font-medium text-muted-foreground ${index === 0 ? '' : 'pt-4'}`}
            >
              {item.section}
            </p>
          ) : null}
          <Link
            activeProps={{
              className: 'bg-accent font-medium text-accent-foreground hover:bg-accent',
            }}
            className="flex min-h-9 items-center gap-2 rounded-md px-3 text-sm text-muted-foreground hover:bg-surface-subtle hover:text-foreground"
            onClick={onNavigate}
            to={item.to}
          >
            {item.icon}
            <span>{item.label}</span>
          </Link>
        </Fragment>
      ))}
    </nav>
  )
}
