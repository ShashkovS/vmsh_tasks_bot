import * as Sentry from '@sentry/react'
import * as contracts from '@vmsh/contracts'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

vi.mock('@sentry/react', () => ({
  init: vi.fn(),
  addBreadcrumb: vi.fn(),
  captureMessage: vi.fn(),
  captureException: vi.fn(),
}))
vi.mock('@vmsh/contracts', async (original) => ({
  ...(await original<typeof contracts>()),
  setServiceEpisodeReporter: vi.fn(),
}))

beforeEach(() => {
  vi.resetModules()
  vi.clearAllMocks()
  vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(Response.json({ allowed: true })))
})

afterEach(() => vi.unstubAllGlobals())

it('keeps disabled clients inert and wires all captures through filtering and privacy', async () => {
  const { initFrontendObservability } = await import('./observability')
  const options = {
    audience: 'student',
    environment: 'test',
    enabled: false,
    dsn: undefined,
  } as const
  initFrontendObservability({ ...options, release: undefined })
  expect(Sentry.init).not.toHaveBeenCalled()
  initFrontendObservability({
    ...options,
    enabled: true,
    dsn: 'https://public@example.test/1',
    release: 'r1',
  })
  initFrontendObservability({
    ...options,
    enabled: true,
    dsn: 'https://public@example.test/1',
    release: 'r1',
  })
  expect(Sentry.init).toHaveBeenCalledTimes(1)
  const config = vi.mocked(Sentry.init).mock.calls[0]?.[0]
  const event = {
    type: undefined,
    fingerprint: ['unexpected'],
    user: { id: 'a1', email: 'secret@example.test' },
    request: { url: 'https://vmsh.example/student?token=secret', data: 'secret answer' },
  }
  const accepted = await config?.beforeSend?.(event, {})
  expect(accepted?.user).toEqual({ id: 'a1' })
  expect(accepted?.request).toEqual({ url: 'https://vmsh.example/student' })
  expect(await config?.beforeSend?.({ ...event }, {})).toBeNull()
  expect(fetch).toHaveBeenCalledTimes(1)
  vi.mocked(fetch).mockResolvedValueOnce(Response.json({ allowed: false }))
  expect(await config?.beforeSend?.({ ...event, fingerprint: ['different'] }, {})).toBeNull()
  expect(fetch).toHaveBeenCalledTimes(2)
  if (typeof config?.integrations !== 'function') throw new Error('Expected integration filter')
  expect(config.integrations([{ name: 'Dedupe' }, { name: 'GlobalHandlers' }])).toEqual([
    { name: 'GlobalHandlers' },
  ])
})

it('keeps all reconnects as breadcrumbs without spending error quota', async () => {
  const { initFrontendObservability } = await import('./observability')
  initFrontendObservability({
    audience: 'staff',
    environment: 'test',
    enabled: true,
    dsn: 'https://public@example.test/1',
    release: 'r1',
  })
  const reporter = vi.mocked(contracts.setServiceEpisodeReporter).mock.calls[0]?.[0]
  reporter?.({ state: 'reconnecting', durationMs: 2_000, prolonged: false })
  reporter?.({ state: 'updating', durationMs: 10_000, prolonged: false })
  expect(Sentry.addBreadcrumb).toHaveBeenCalledTimes(2)
  expect(Sentry.captureMessage).not.toHaveBeenCalled()
  reporter?.({ state: 'reconnecting', durationMs: 60_000, prolonged: true })
  expect(Sentry.addBreadcrumb).toHaveBeenCalledTimes(3)
  expect(Sentry.captureMessage).not.toHaveBeenCalled()
  expect(fetch).not.toHaveBeenCalled()
})
