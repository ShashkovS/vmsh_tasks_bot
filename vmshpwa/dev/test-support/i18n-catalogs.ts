import type { Messages } from '@lingui/core'
import type { CatalogLoaders } from '@vmsh/i18n'

/**
 * Every catalog of the workspace merged per locale, for Vitest and Storybook,
 * which render components of all apps. Apps merge only their own catalogs in
 * `apps/<app>/src/i18n/`. See `docs/i18n.md`.
 */
function merge(modules: Record<string, { messages: Messages }>): Promise<{ messages: Messages }> {
  const messages: Messages = {}
  for (const module of Object.values(modules)) Object.assign(messages, module.messages)
  return Promise.resolve({ messages })
}

export const allCatalogLoaders: CatalogLoaders = {
  ru: () =>
    merge(
      import.meta.glob<{ messages: Messages }>(
        ['../../apps/*/src/locales/ru.po', '../../packages/*/src/locales/ru.po'],
        { eager: true },
      ),
    ),
  en: () =>
    merge(
      import.meta.glob<{ messages: Messages }>(
        ['../../apps/*/src/locales/en.po', '../../packages/*/src/locales/en.po'],
        { eager: true },
      ),
    ),
}
