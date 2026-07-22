import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    name: 'unit',
    environment: 'jsdom',
    include: ['packages/**/*.test.{ts,tsx}', 'apps/**/*.test.{ts,tsx}'],
    coverage: { provider: 'v8', reporter: ['text', 'html'], reportsDirectory: './coverage/unit' },
  },
})
