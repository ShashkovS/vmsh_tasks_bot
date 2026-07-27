import { defineConfig, devices } from '@playwright/test'
import { randomUUID } from 'node:crypto'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const workspace = path.dirname(fileURLToPath(import.meta.url))
const repository = path.resolve(workspace, '..')
const apiOrigin = 'http://127.0.0.1:8380'
const gatewayOrigin = 'http://127.0.0.1:5380'
const gatewayControlToken = process.env.VMSH_E2E_GATEWAY_CONTROL_TOKEN ?? randomUUID()

// Test workers inherit this ephemeral capability while the gateway receives
// the same value explicitly below. It grants only loopback SW-generation
// control and may be visible in a retained Playwright trace; it never enters a
// frontend bundle or grants product access. See e2e/runtime-isolation.spec.ts.
process.env.VMSH_E2E_GATEWAY_CONTROL_TOKEN = gatewayControlToken

const backendEnv = {
  ...process.env,
  UV_CACHE_DIR: path.resolve(repository, '.runtime/uv-cache'),
  VMSH_RUNTIME_PROFILE: 'pwa-e2e',
  VMSH_INSTANCE: 'e2e',
  VMSH_DB_FILENAME: 'db/vmshpwa_e2e.sqlite3',
  VMSH_MEDIA_ROOT: '.runtime/vmshpwa/e2e',
  VMSH_NATS_SERVER: '',
  VMSH_NATS_TOPIC_PREFIX: 'vmshpwa_e2e',
  VMSH_PWA_PROTOTYPE: 'true',
  VMSH_API_PORT: '8380',
}

export default defineConfig({
  testDir: './e2e',
  outputDir: './test-results',
  // Keep tests within a project sequential. Firefox serializes service-worker
  // installation internally, so parallel registrations from isolated contexts
  // can exceed the activation timeout even though each worker is valid.
  // Browser projects still run in parallel with one another.
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  snapshotPathTemplate: '{testDir}/__screenshots__/{testFilePath}/{arg}-{projectName}{ext}',
  use: {
    baseURL: gatewayOrigin,
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
      // A clean checkout has no runtime DB. Seed is the explicit maintenance
      // boundary; aiohttp startup itself only verifies schema (ADR 0002).
      command: 'uv run python -m vmshpwa.scripts.seed_runtime && uv run python main.py',
      cwd: repository,
      env: backendEnv,
      url: `${apiOrigin}/student/api/v1/health`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command:
        'uv run python -m vmshpwa.scripts.e2e_gateway --host 127.0.0.1 --port 5380 --workspace vmshpwa --api-origin http://127.0.0.1:8380',
      cwd: repository,
      env: {
        ...process.env,
        UV_CACHE_DIR: path.resolve(repository, '.runtime/uv-cache'),
        VMSH_RUNTIME_PROFILE: 'pwa-e2e',
        VMSH_E2E_GATEWAY_CONTROL_TOKEN: gatewayControlToken,
      },
      url: `${gatewayOrigin}/__e2e__/health`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
})
