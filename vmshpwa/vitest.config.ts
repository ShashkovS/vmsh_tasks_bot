import { fileURLToPath } from 'node:url'

import { defineConfig } from 'vitest/config'

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
    name: 'unit',
    environment: 'jsdom',
    include: ['packages/**/*.test.{ts,tsx}', 'apps/**/*.test.{ts,tsx}'],
    setupFiles: ['./dev/test-support/i18n-setup.ts'],
    coverage: { provider: 'v8', reporter: ['text', 'html'], reportsDirectory: './coverage/unit' },
  },
})
