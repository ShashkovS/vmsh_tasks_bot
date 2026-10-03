import { defineConfig } from '@playwright/test'
import base from './playwright.config'

// Seed the large report before the runtime acquires its lifecycle lock.
export default defineConfig({
  ...base,
  testIgnore: [],
  testMatch: ['statistics-reports.spec.ts', 'statistics-recalculation.spec.ts'],
  webServer: (Array.isArray(base.webServer) ? base.webServer : []).map((server) => ({
    ...server,
    command: server.command.replace(
      'uv run python main.py',
      'uv run python -m vmshpwa.scripts.seed_e2e_statistics_reports && uv run python main.py',
    ),
  })),
})
