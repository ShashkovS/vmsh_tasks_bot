import { defineConfig } from '@playwright/test'
import base from './playwright.config'

// Seed the large report before the runtime acquires its lifecycle lock.
export default defineConfig({
  ...base,
  testIgnore: [],
  testMatch: ['statistics-reports.spec.ts', 'statistics-recalculation.spec.ts'],
  webServer: (Array.isArray(base.webServer) ? base.webServer : []).map((server) => ({
    ...server,
    env: { ...server.env, VMSH_E2E_LARGE_STATISTICS: '1' },
  })),
})
