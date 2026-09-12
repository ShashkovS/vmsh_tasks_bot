import { fileURLToPath } from 'node:url'

import { defineConfig } from 'vitest/config'

export default defineConfig({
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
    coverage: { provider: 'v8', reporter: ['text', 'html'], reportsDirectory: './coverage/unit' },
  },
})
