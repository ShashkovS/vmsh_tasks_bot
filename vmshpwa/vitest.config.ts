import { fileURLToPath } from 'node:url'

import { configDefaults, defineConfig } from 'vitest/config'

import { i18nPlugins } from './vite-i18n'

export default defineConfig({
  plugins: i18nPlugins(),
  resolve: {
    alias: {
      'virtual:pwa-register/react': fileURLToPath(
        new URL('./dev/test-support/virtual-pwa-register-react.ts', import.meta.url),
      ),
    },
  },
  test: {
    maxWorkers: 2,
    // testing-strategy.md: pure contracts need neither a DOM nor every app's
    // translations. Keep both projects in `pnpm test` and coverage inventory.
    projects: [
      {
        extends: true,
        test: {
          name: 'unit',
          environment: 'jsdom',
          include: ['packages/**/*.test.{ts,tsx}', 'apps/**/*.test.{ts,tsx}'],
          exclude: [...configDefaults.exclude, 'packages/contracts/**/*.test.ts'],
          setupFiles: ['./dev/test-support/i18n-setup.ts'],
        },
      },
      {
        extends: true,
        test: {
          name: 'unit-contracts',
          environment: 'node',
          include: ['packages/contracts/**/*.test.ts'],
          setupFiles: [],
        },
      },
    ],
    coverage: { provider: 'v8', reporter: ['text', 'html'], reportsDirectory: './coverage/unit' },
  },
})
