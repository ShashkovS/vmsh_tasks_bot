import { beforeEach, describe, expect, it, vi } from 'vitest'

beforeEach(() => {
  vi.resetModules()
  vi.restoreAllMocks()
})

describe('bounded photo failure diagnostics', () => {
  it('keeps the error, sends no URL, and caps repeated failures', async () => {
    const { observeMediaLoad } = await import('./product-analytics')
    const dispatch = vi.spyOn(window, 'dispatchEvent')
    let now = 0
    vi.spyOn(performance, 'now').mockImplementation(() => now)
    const failure = new Error('private signed URL must not be reported')
    const fail = () => Promise.reject(failure)
    for (let index = 0; index < 15; index += 1) {
      await expect(observeMediaLoad(fail)).rejects.toBe(failure)
    }
    expect(dispatch).toHaveBeenCalledTimes(1)
    for (let index = 0; index < 15; index += 1) {
      now += 60_001
      await expect(observeMediaLoad(fail)).rejects.toBe(failure)
    }
    expect(dispatch).toHaveBeenCalledTimes(10)
    expect((dispatch.mock.calls[0]![0] as CustomEvent).detail).toEqual({
      eventType: 'media.load.failed',
      entity: undefined,
    })
  })
  it('does not report successful loads or cancellation', async () => {
    const { observeMediaLoad } = await import('./product-analytics')
    const dispatch = vi.spyOn(window, 'dispatchEvent')
    await expect(observeMediaLoad(() => Promise.resolve('photo'))).resolves.toBe('photo')
    const abort = new DOMException('cancelled', 'AbortError')
    await expect(observeMediaLoad(() => Promise.reject(abort))).rejects.toBe(abort)
    expect(dispatch).not.toHaveBeenCalled()
  })
})
