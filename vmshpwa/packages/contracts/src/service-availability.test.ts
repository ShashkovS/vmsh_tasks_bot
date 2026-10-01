import { afterEach, expect, it, vi } from 'vitest'
import { createServiceTransport } from './service-availability'

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})
const updating = () =>
  new Response(JSON.stringify({ error: { code: 'service_updating' } }), { status: 503 })
function fixture() {
  vi.useFakeTimers()
  let mode: 'ready' | 'updating' | 'bad-gateway' = 'updating'
  const fetch = vi.fn<typeof globalThis.fetch>((input) => {
    if (input === '/service-status')
      return Promise.resolve(Response.json({ state: mode === 'updating' ? 'updating' : 'ready' }))
    return Promise.resolve(
      mode === 'updating'
        ? updating()
        : mode === 'bad-gateway'
          ? new Response('<html>bad gateway</html>', { status: 502 })
          : Response.json({ ok: true }),
    )
  })
  const episode = vi.fn()
  const transport = createServiceTransport({
    fetch,
    origin: 'https://school.test',
    random: () => 0,
    onEpisode: episode,
  })
  return {
    fetch,
    episode,
    transport,
    setMode: (next: typeof mode) => {
      mode = next
    },
  }
}
it('shares one recovery loop and preserves a marked write during a 20 second deploy', async () => {
  const f = fixture()
  const body = JSON.stringify({ text: 'draft' })
  const a = f.transport.fetch('/student/api/v1/runtime')
  const b = f.transport.fetch('/staff/api/v1/save', { method: 'POST', body })
  await vi.advanceTimersByTimeAsync(20_000)
  expect(f.transport.getSnapshot().state).toBe('updating')
  expect(f.fetch.mock.calls.filter(([url]) => url === '/service-status')).toHaveLength(5)
  expect(f.fetch.mock.calls.filter(([url]) => url === '/staff/api/v1/save')).toHaveLength(1)
  f.setMode('ready')
  await vi.advanceTimersByTimeAsync(5_000)
  expect((await a).status).toBe(200)
  expect((await b).status).toBe(200)
  expect(f.fetch.mock.calls.filter(([url]) => url === '/staff/api/v1/save')[1]?.[1]?.body).toBe(
    body,
  )
  expect(f.transport.getSnapshot().state).toBe('ready')
})
it('does not replay an ambiguous write, but resumes an explicit receipt-backed operation', async () => {
  const f = fixture()
  f.setMode('bad-gateway')
  const result = await f.transport.fetch('/staff/api/v1/import', { method: 'POST', body: '{}' })
  expect((await result.json()).error.code).toBe('request_not_confirmed')
  f.setMode('ready')
  await vi.advanceTimersByTimeAsync(1_000)
  expect(f.fetch.mock.calls.filter(([url]) => url === '/staff/api/v1/import')).toHaveLength(1)
  f.setMode('bad-gateway')
  const body = JSON.stringify({ operationId: 'op-1' })
  const saved = f.transport.fetch('/staff/api/v1/live-marking/operations', { method: 'POST', body })
  await vi.advanceTimersByTimeAsync(1_000)
  f.setMode('ready')
  await vi.advanceTimersByTimeAsync(2_000)
  expect((await saved).ok).toBe(true)
  const writes = f.fetch.mock.calls.filter(
    ([url]) => url === '/staff/api/v1/live-marking/operations',
  )
  expect(writes).toHaveLength(2)
  expect(writes[0]?.[1]?.body).toBe(writes[1]?.[1]?.body)
})
it('keeps waiting past sixty seconds and supports cancellation without another probe loop', async () => {
  const f = fixture()
  const controller = new AbortController()
  const pending = f.transport.fetch('/student/api/v1/runtime', { signal: controller.signal })
  const rejected = expect(pending).rejects.toMatchObject({ name: 'AbortError' })
  await vi.advanceTimersByTimeAsync(61_000)
  expect(f.transport.getSnapshot()).toMatchObject({ state: 'updating', prolonged: true })
  controller.abort()
  await rejected
  f.setMode('ready')
  await vi.advanceTimersByTimeAsync(5_000)
  expect(f.transport.getSnapshot().state).toBe('ready')
  expect(f.episode).toHaveBeenCalledTimes(1)
})
it('does not intercept storage origins, business errors or invalid successful runtime', async () => {
  const fetch = vi
    .fn<typeof globalThis.fetch>()
    .mockResolvedValue(new Response('invalid', { status: 200 }))
  const t = createServiceTransport({ fetch, origin: 'https://school.test' })
  expect(await (await t.fetch('https://storage.test/photo')).text()).toBe('invalid')
  for (const status of [200, 401, 403, 409, 422, 429]) {
    fetch.mockResolvedValueOnce(new Response('unchanged', { status }))
    const response = await t.fetch('/family/api/v1/runtime')
    expect(response.status).toBe(status)
    expect(await response.text()).toBe('unchanged')
  }
  expect(t.getSnapshot().state).toBe('ready')
})

it.each([502, 503, 504])(
  'preserves a structured API failure with HTTP %s without recovery or replay',
  async (status) => {
    const payload = {
      error: {
        code: 'metadata_generation_failed',
        message: 'Could not generate metadata. Try again.',
        requestId: 'request-123',
      },
    }
    const fetch = vi
      .fn<typeof globalThis.fetch>()
      .mockResolvedValue(Response.json(payload, { status }))
    const transport = createServiceTransport({ fetch, origin: 'https://school.test' })
    const response = await transport.fetch(
      '/staff/api/v1/group-lessons/gl-1/metadata-grid/generate',
      { method: 'POST', body: '{}' },
    )
    expect(response.status).toBe(status)
    expect(await response.json()).toEqual(payload)
    expect(fetch).toHaveBeenCalledTimes(1)
    expect(transport.getSnapshot().state).toBe('ready')
  },
)

it('uses the current UI translation for ambiguous writes and keeps recovery running', async () => {
  vi.useFakeTimers()
  let message = 'The server did not confirm the action.'
  const fetch = vi
    .fn<typeof globalThis.fetch>()
    .mockResolvedValueOnce(new Response('gateway', { status: 502 }))
    .mockImplementation(() => Promise.resolve(Response.json({ state: 'ready' })))
  const transport = createServiceTransport({
    fetch,
    origin: 'https://school.test',
    random: () => 0,
    unconfirmedMessage: () => message,
  })
  const first = await transport.fetch('/staff/api/v1/save', { method: 'POST' })
  expect((await first.json()).error.message).toBe(message)
  expect(transport.getSnapshot().state).toBe('reconnecting')
  await vi.advanceTimersByTimeAsync(1000)
  message = 'Сервер не подтвердил действие.'
  fetch.mockResolvedValueOnce(new Response('gateway', { status: 502 }))
  const second = await transport.fetch('/staff/api/v1/save', { method: 'POST' })
  expect((await second.json()).error.message).toBe(message)
  await vi.advanceTimersByTimeAsync(1000)
})

it.each([
  ['/student/api/v1/auth/me', undefined],
  [
    '/student/api/v1/problems/p-1/test-attempts',
    { method: 'POST', body: JSON.stringify({ idempotencyKey: 'offline-answer' }) },
  ],
])('allows offline cache/outbox boundaries during recovery: %s', async (path, init) => {
  const f = fixture()
  const first = f.transport.fetch('/student/api/v1/runtime')
  await vi.advanceTimersByTimeAsync(1_000)
  vi.stubGlobal('navigator', { onLine: false })
  const callsBefore = f.fetch.mock.calls.length
  await expect(f.transport.fetch(path, init)).rejects.toBeInstanceOf(TypeError)
  expect(f.fetch.mock.calls).toHaveLength(callsBefore)
  vi.stubGlobal('navigator', { onLine: true })
  f.setMode('ready')
  await vi.advanceTimersByTimeAsync(2_000)
  expect((await first).ok).toBe(true)
})

it('recovers against an old installation returning HTML for the unknown status route', async () => {
  vi.useFakeTimers()
  const fetch = vi
    .fn<typeof globalThis.fetch>()
    .mockResolvedValueOnce(new Response('bad gateway', { status: 502 }))
    .mockResolvedValueOnce(new Response('<html>Old landing page</html>'))
    .mockResolvedValueOnce(Response.json({ ready: true }))
    .mockResolvedValueOnce(Response.json({ ready: true }))
  const t = createServiceTransport({ fetch, origin: 'https://school.test', random: () => 0 })
  const result = t.fetch('/family/api/v1/runtime')
  await vi.advanceTimersByTimeAsync(1500)
  expect((await result).ok).toBe(true)
  expect(t.getSnapshot().state).toBe('ready')
})

it('lets cache-backed reads fall back when the browser reports online but the network is unreachable', async () => {
  vi.useFakeTimers()
  vi.stubGlobal('navigator', { onLine: true })
  const transport = createServiceTransport({
    origin: 'https://school.test',
    fetch: vi.fn(() => Promise.reject(new TypeError('unreachable'))),
  })
  await expect(transport.fetchOfflineRead('/student/api/v1/home')).rejects.toThrow('unreachable')
  // Later cache-backed requests must not hang behind the background recovery loop.
  await expect(transport.fetchOfflineRead('/student/api/v1/courses')).rejects.toThrow(
    'Network recovery',
  )
})

it('keeps explicit deploy recovery for cache-backed reads', async () => {
  const f = fixture()
  const pending = f.transport.fetchOfflineRead('/student/api/v1/home')
  await vi.advanceTimersByTimeAsync(5_000)
  expect(f.transport.getSnapshot().state).toBe('updating')
  f.setMode('ready')
  await vi.advanceTimersByTimeAsync(5_000)
  expect((await pending).status).toBe(200)
})
