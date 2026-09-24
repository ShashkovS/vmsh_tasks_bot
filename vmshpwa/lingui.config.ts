import { defineConfig } from '@lingui/conf'
import { formatter } from '@lingui/format-po'

/**
 * Every package or app with product copy owns one catalog, so a shared string
 * is translated once. Each app merges the catalogs of its `@vmsh/*` packages
 * in `apps/<app>/src/i18n/catalog-<locale>.ts`.
 * See `adr/0004-pwa-internationalization.md` and `docs/i18n.md`.
 */
export const catalogOwners = [
  'packages/ui',
  'packages/content',
  'packages/product',
  'packages/app-shell',
  'apps/student',
  'apps/family',
  'apps/staff',
  'apps/landing',
] as const

export default defineConfig({
  sourceLocale: 'ru',
  locales: ['ru', 'en'],
  catalogs: catalogOwners.map((owner) => ({
    path: `<rootDir>/${owner}/src/locales/{locale}`,
    include: [`<rootDir>/${owner}/src`],
    exclude: [
      '**/*.test.ts',
      '**/*.test.tsx',
      '**/*.stories.ts',
      '**/*.stories.tsx',
      '**/routeTree.gen.ts',
      '**/locales/**',
    ],
  })),
  // Origins without line numbers keep catalog diffs small; origins are still
  // needed by `scripts/i18n-check.mjs` to enforce coverage per scope.
  format: formatter({ lineNumbers: false }),
  orderBy: 'message',
})
