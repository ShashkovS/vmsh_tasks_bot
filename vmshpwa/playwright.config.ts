import { defineConfig, devices } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const workspace = path.dirname(fileURLToPath(import.meta.url))
const repository = path.resolve(workspace, '..')
const apiOrigin = 'http://127.0.0.1:8380'

const backendEnv = {
  ...process.env,
  VMSH_RUNTIME_PROFILE: 'pwa-e2e',
  VMSH_INSTANCE: 'e2e',
  VMSH_DB_FILENAME: 'db/vmshpwa_e2e.sqlite3',
  VMSH_MEDIA_ROOT: '.runtime/vmshpwa/e2e',
  VMSH_NATS_TOPIC_PREFIX: 'vmshpwa_e2e',
  VMSH_PWA_PROTOTYPE: 'true',
  VMSH_API_PORT: '8380',
}

export default defineConfig({
  testDir: './e2e',
  outputDir: './test-results',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  snapshotPathTemplate: '{testDir}/__screenshots__/{testFilePath}/{arg}-{projectName}{ext}',
  use: {
    locale: 'ru-RU',
    timezoneId: 'Europe/Moscow',
    colorScheme: 'light',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  expect: {
    toHaveScreenshot: { animations: 'disabled', caret: 'hide', maxDiffPixelRatio: 0.01 },
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'webkit', use: { ...devices['Desktop Safari'] } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
  ],
  webServer: [
    {
      command: 'uv run python main.py',
      cwd: repository,
      env: backendEnv,
      url: `${apiOrigin}/student/api/v1/health`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: 'pnpm --filter @vmsh/student dev',
      cwd: workspace,
      env: {
        ...process.env,
        VITE_PORT: '5373',
        VMSH_API_ORIGIN: apiOrigin,
        VMSH_PWA_DEV_SW: '1',
      },
      url: 'http://127.0.0.1:5373/student/',
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: 'pnpm --filter @vmsh/family dev',
      cwd: workspace,
      env: {
        ...process.env,
        VITE_PORT: '5374',
        VMSH_API_ORIGIN: apiOrigin,
        VMSH_PWA_DEV_SW: '1',
      },
      url: 'http://127.0.0.1:5374/family/',
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: 'pnpm --filter @vmsh/staff dev',
      cwd: workspace,
      env: { ...process.env, VITE_PORT: '5375', VMSH_API_ORIGIN: apiOrigin },
      url: 'http://127.0.0.1:5375/staff/',
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
})
