import type { CatalogLoaders } from '@vmsh/i18n'

/**
 * One chunk per locale. The Russian chunk is preloaded from `index.html` by
 * `vite-i18n.ts`; both are precached by the service worker for offline starts.
 */
export const catalogLoaders: CatalogLoaders = {
  ru: () => import('./catalog-ru'),
  en: () => import('./catalog-en'),
}
