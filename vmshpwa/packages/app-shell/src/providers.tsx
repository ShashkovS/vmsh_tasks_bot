import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Moon, Sun } from 'lucide-react'
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

import { Button, Toaster, TooltipProvider } from '@vmsh/ui'

type Theme = 'light' | 'dark'
type StorageNamespace = 'student' | 'family' | 'staff' | 'storybook'

const StorageNamespaceContext = createContext<StorageNamespace>('storybook')

function initialTheme(storageNamespace: StorageNamespace): Theme {
  if (typeof window === 'undefined') return 'light'
  const stored = window.localStorage.getItem(`vmsh-${storageNamespace}-theme`)
  if (stored === 'light' || stored === 'dark') return stored
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function AppProviders({
  children,
  storageNamespace = 'storybook',
}: {
  children: ReactNode
  storageNamespace?: StorageNamespace
}) {
  const queryClient = useMemo(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false },
          mutations: { retry: 0 },
        },
      }),
    [],
  )

  return (
    <StorageNamespaceContext value={storageNamespace}>
      <QueryClientProvider client={queryClient}>
        <TooltipProvider>
          {children}
          <Toaster />
        </TooltipProvider>
      </QueryClientProvider>
    </StorageNamespaceContext>
  )
}

export function ThemeToggle() {
  const storageNamespace = useContext(StorageNamespaceContext)
  const [theme, setTheme] = useState<Theme>(() => initialTheme(storageNamespace))

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
    document.documentElement.style.colorScheme = theme
    window.localStorage.setItem(`vmsh-${storageNamespace}-theme`, theme)
  }, [storageNamespace, theme])

  const nextTheme = theme === 'dark' ? 'light' : 'dark'

  return (
    <Button
      aria-label={`Переключить на ${nextTheme === 'dark' ? 'тёмную' : 'светлую'} тему`}
      size="icon-sm"
      variant="ghost"
      onClick={() => setTheme(nextTheme)}
    >
      {theme === 'dark' ? <Sun aria-hidden="true" /> : <Moon aria-hidden="true" />}
    </Button>
  )
}
