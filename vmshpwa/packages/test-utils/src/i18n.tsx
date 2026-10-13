import { render, type RenderOptions, type RenderResult } from '@testing-library/react'
import type { ReactElement, ReactNode } from 'react'

import { LocaleProvider, type CatalogLoaders } from '@vmsh/i18n'

/**
 * Catalogs are preloaded once by `dev/test-support/i18n-setup.ts` (Vitest) or
 * the Storybook decorator, so these loaders only let `changeLocale` activate
 * an already loaded language. Loading an empty object merges nothing.
 */
const preloadedCatalogLoaders: CatalogLoaders = {
  ru: () => Promise.resolve({ messages: {} }),
  en: () => Promise.resolve({ messages: {} }),
}

/** Provides Lingui and locale context to components that use `<Trans>` or `useLingui`. */
export function I18nTestProvider({ children }: { children: ReactNode }) {
  return <LocaleProvider loaders={preloadedCatalogLoaders}>{children}</LocaleProvider>
}

export function renderWithI18n(ui: ReactElement, options: RenderOptions = {}): RenderResult {
  const { wrapper: Wrapper, ...rest } = options
  return render(ui, {
    ...rest,
    wrapper: ({ children }: { children: ReactNode }) => (
      <I18nTestProvider>{Wrapper ? <Wrapper>{children}</Wrapper> : children}</I18nTestProvider>
    ),
  })
}
