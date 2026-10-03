import { i18n } from '@lingui/core'
import { I18nProvider } from '@lingui/react'
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from 'react'

import { activateLocale, currentLocale, type CatalogLoaders } from './activation'
import type { Locale } from './locale'
import { writeLocaleCookie } from './locale-cookie'

export interface LocaleContextValue {
  locale: Locale
  /** True while the catalog of a newly selected language is loading. */
  changing: boolean
  /**
   * Switches the interface language on this device without a reload. The
   * account preference is saved by `@vmsh/app-shell`, which owns the API.
   */
  changeLocale: (locale: Locale) => Promise<void>
}

const LocaleContext = createContext<LocaleContextValue | null>(null)

function subscribe(onChange: () => void): () => void {
  return i18n.on('change', onChange)
}

/**
 * Outermost provider of every app: startup, update and offline fallback
 * screens render above `AppProviders`, so translation must wrap them too.
 * Activate a locale with `bootstrapLocale` before the first render.
 */
export function LocaleProvider({
  children,
  loaders,
}: {
  children: ReactNode
  loaders: CatalogLoaders
}) {
  const locale = useSyncExternalStore(subscribe, currentLocale, currentLocale)
  const [changing, setChanging] = useState(false)

  const changeLocale = useCallback(
    async (next: Locale) => {
      if (next === currentLocale()) {
        writeLocaleCookie(next)
        return
      }
      setChanging(true)
      try {
        await activateLocale(next, loaders)
        writeLocaleCookie(next)
      } finally {
        setChanging(false)
      }
    },
    [loaders],
  )

  const value = useMemo(
    () => ({ locale, changing, changeLocale }),
    [locale, changing, changeLocale],
  )

  return (
    <LocaleContext value={value}>
      <I18nProvider i18n={i18n}>{children}</I18nProvider>
    </LocaleContext>
  )
}

export function useLocale(): LocaleContextValue {
  const value = useContext(LocaleContext)
  if (!value) throw new Error('useLocale requires LocaleProvider')
  return value
}
