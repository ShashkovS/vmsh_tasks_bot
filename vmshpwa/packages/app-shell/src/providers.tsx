import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Moon, Sun } from 'lucide-react'
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

import { Button, Toaster, TooltipProvider } from '@vmsh/ui'
import type { BrowserStorageNamespace } from '@vmsh/contracts'

type Theme = 'light' | 'dark'
export const STORYBOOK_STORAGE_NAMESPACE = 'vmsh-179:storybook:default' as const
type StorageNamespace = BrowserStorageNamespace | typeof STORYBOOK_STORAGE_NAMESPACE

const StorageNamespaceContext = createContext<StorageNamespace>(STORYBOOK_STORAGE_NAMESPACE)

export function themeStorageKey(storageNamespace: StorageNamespace): string {
  return `${storageNamespace}:theme`
}

function readTheme(storageNamespace: StorageNamespace): Theme | null {
  try {
    const stored = window.localStorage.getItem(themeStorageKey(storageNamespace))
    return stored === 'light' || stored === 'dark' ? stored : null
  } catch {
    // Theme is a convenience, not user work. Storage-denied/private contexts
    // must keep the shell usable; durable drafts use the explicit Dexie gate.
    return null
  }
}

function persistTheme(storageNamespace: StorageNamespace, theme: Theme): void {
  try {
    window.localStorage.setItem(themeStorageKey(storageNamespace), theme)
  } catch {
    // Keep the in-memory theme for this page without turning a cosmetic
    // preference failure into an application startup failure.
  }
}

function initialTheme(storageNamespace: StorageNamespace): Theme {
  if (typeof window === 'undefined') return 'light'
  const stored = readTheme(storageNamespace)
  if (stored) return stored
  return typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-color-scheme: dark)').matches
    ? 'dark'
    : 'light'
}

export function AppProviders({
  children,
  storageNamespace = STORYBOOK_STORAGE_NAMESPACE,
  queryClient: providedQueryClient,
}: {
  children: ReactNode
  storageNamespace?: StorageNamespace
  queryClient?: QueryClient
}) {
  const defaultQueryClient = useMemo(() => createAppQueryClient(), [])
  const queryClient = providedQueryClient ?? defaultQueryClient

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

export function createAppQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false },
      mutations: { retry: 0 },
    },
  })
}

export function ThemeToggle() {
  const storageNamespace = useContext(StorageNamespaceContext)
  const [theme, setTheme] = useState<Theme>(() => initialTheme(storageNamespace))

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
    document.documentElement.style.colorScheme = theme
    persistTheme(storageNamespace, theme)
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
