import { afterEach, describe, expect, it, vi } from 'vitest'
import { activatePwaUpdate } from './pwa-update-activation'

class Worker extends EventTarget {
  postMessage = vi.fn()
  constructor(public state: ServiceWorkerState = 'installed') {
    super()
  }
}
function fixture() {
  const active = new Worker('activated')
  const waiting = new Worker()
  const registration: EventTarget & {
    active: Worker
    waiting: Worker | null
    installing: Worker | null
  } = Object.assign(new EventTarget(), {
    active,
    waiting,
    installing: null,
  })
  const container = Object.assign(new EventTarget(), {
    controller: active,
    getRegistration: vi.fn().mockResolvedValue(registration),
  })
  const signal = new AbortController()
  const start = () =>
    activatePwaUpdate({
      container: container as unknown as ServiceWorkerContainer,
      href: 'https://example.test/student/tasks',
      signal: signal.signal,
      timeoutMs: 100,
    })
  return { active, waiting, registration, container, signal, start }
}
afterEach(() => vi.useRealTimers())

describe('PWA activation (docs/runtime-isolation.md)', () => {
  it('waits for control, not just a successful SKIP_WAITING post', async () => {
    const f = fixture()
    const done = vi.fn()
    const result = f.start().then(done)
    await vi.waitFor(() =>
      expect(f.waiting.postMessage).toHaveBeenCalledWith({ type: 'SKIP_WAITING' }),
    )
    expect(done).not.toHaveBeenCalled()
    f.container.controller = f.waiting
    f.container.dispatchEvent(new Event('controllerchange'))
    await result
    expect(done).toHaveBeenCalledOnce()
  })
  it('allows reload when another tab has already activated the worker', async () => {
    const f = fixture()
    f.registration.waiting = null
    await expect(f.start()).resolves.toBeUndefined()
    expect(f.waiting.postMessage).not.toHaveBeenCalled()
  })
  it('does not lose controllerchange while registration lookup is pending', async () => {
    const f = fixture()
    f.container.getRegistration.mockReturnValue(new Promise(() => undefined))
    const result = f.start()
    f.container.controller = f.waiting
    f.container.dispatchEvent(new Event('controllerchange'))
    await expect(result).resolves.toBeUndefined()
  })
  it('waits for an installing worker, then activates it', async () => {
    const f = fixture()
    f.waiting.state = 'installing'
    f.registration.installing = f.waiting
    f.registration.waiting = null
    const result = f.start()
    await vi.waitFor(() => expect(f.container.getRegistration).toHaveBeenCalled())
    expect(f.waiting.postMessage).not.toHaveBeenCalled()
    f.registration.installing = null
    f.registration.waiting = f.waiting
    f.waiting.state = 'installed'
    f.waiting.dispatchEvent(new Event('statechange'))
    expect(f.waiting.postMessage).toHaveBeenCalledOnce()
    f.container.controller = f.waiting
    f.container.dispatchEvent(new Event('controllerchange'))
    await result
  })
  it('times out a silent worker, removes listeners and permits a retry', async () => {
    vi.useFakeTimers()
    const f = fixture()
    const remove = vi.spyOn(f.container, 'removeEventListener')
    const error = expect(f.start()).rejects.toThrow('timed out')
    await vi.advanceTimersByTimeAsync(100)
    await error
    expect(remove).toHaveBeenCalledWith('controllerchange', expect.any(Function))
    const retry = f.start()
    await vi.advanceTimersByTimeAsync(0)
    expect(f.waiting.postMessage).toHaveBeenCalledTimes(2)
    f.container.controller = f.waiting
    f.container.dispatchEvent(new Event('controllerchange'))
    await retry
  })
  it('reports missing registration and registration lookup failures', async () => {
    const f = fixture()
    f.container.getRegistration.mockResolvedValueOnce(undefined)
    await expect(f.start()).rejects.toThrow('No service worker')
    f.container.getRegistration.mockRejectedValueOnce(new Error('lookup failed'))
    await expect(f.start()).rejects.toThrow('lookup failed')
  })
  it('cancels on unmount without leaving an activation listener', async () => {
    const f = fixture()
    const result = expect(f.start()).rejects.toThrow('cancelled')
    f.signal.abort()
    await result
    expect(f.waiting.postMessage).not.toHaveBeenCalled()
  })
})
