import { act, cleanup, render } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { VisibleSupportReply } from './visible-support-reply'

// docs/question-attention.md: timing includes hiding, tall replies and retry.
let top = 10
let height = 100
beforeEach(() => {
  vi.useFakeTimers()
  top = 10
  height = 100
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(() => ({
    top,
    bottom: top + height,
    height,
    width: 100,
    left: 0,
    right: 100,
    x: 0,
    y: top,
    toJSON: () => ({}),
  }))
  vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')
  vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(true)
})
afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.restoreAllMocks()
})
const tick = async (ms: number) => {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms)
  })
}

describe('support reply visibility', () => {
  it('requires continuous visibility and acknowledges once', async () => {
    const onRead = vi.fn().mockResolvedValue({})
    render(
      <VisibleSupportReply entryId="sue-1" unread onRead={onRead}>
        Ответ
      </VisibleSupportReply>,
    )
    await tick(2_000)
    top = window.innerHeight + 1
    await act(() => document.dispatchEvent(new Event('scroll')))
    await tick(5_000)
    expect(onRead).not.toHaveBeenCalled()
    top = 10
    await act(() => document.dispatchEvent(new Event('scroll')))
    await tick(2_999)
    expect(onRead).not.toHaveBeenCalled()
    await tick(1)
    expect(onRead).toHaveBeenCalledExactlyOnceWith('sue-1')
    await tick(10_000)
    expect(onRead).toHaveBeenCalledTimes(1)
  })
  it('resets when the tab is hidden and cancels on collapse', async () => {
    const onRead = vi.fn().mockResolvedValue({})
    const view = render(
      <VisibleSupportReply entryId="sue-1" unread onRead={onRead}>
        Ответ
      </VisibleSupportReply>,
    )
    await tick(2_000)
    vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('hidden')
    await act(() => document.dispatchEvent(new Event('visibilitychange')))
    await tick(5_000)
    expect(onRead).not.toHaveBeenCalled()
    vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')
    await act(() => document.dispatchEvent(new Event('visibilitychange')))
    await tick(2_000)
    view.unmount()
    await tick(5_000)
    expect(onRead).not.toHaveBeenCalled()
  })
  it('handles a reply taller than the viewport and retries failed acknowledgements', async () => {
    height = window.innerHeight * 3
    const onRead = vi.fn().mockRejectedValueOnce(new Error('offline')).mockResolvedValue({})
    render(
      <VisibleSupportReply entryId="sue-2" unread onRead={onRead}>
        Длинный ответ
      </VisibleSupportReply>,
    )
    await tick(3_000)
    expect(onRead).toHaveBeenCalledTimes(1)
    await tick(7_999)
    expect(onRead).toHaveBeenCalledTimes(1)
    await tick(1)
    expect(onRead).toHaveBeenCalledTimes(2)
  })
  it('does not acknowledge read or unknown legacy entries', async () => {
    const onRead = vi.fn()
    render(
      <VisibleSupportReply entryId="sue-3" unread={false} onRead={onRead}>
        Ответ
      </VisibleSupportReply>,
    )
    await tick(20_000)
    expect(onRead).not.toHaveBeenCalled()
  })
  it('requires the 75% boundary and resets visibility when offline', async () => {
    top = window.innerHeight - 74
    const onRead = vi.fn().mockResolvedValue({})
    render(
      <VisibleSupportReply entryId="sue-4" unread onRead={onRead}>
        Ответ
      </VisibleSupportReply>,
    )
    await tick(4_000)
    expect(onRead).not.toHaveBeenCalled()
    top = window.innerHeight - 75
    await act(() => document.dispatchEvent(new Event('scroll')))
    await tick(2_000)
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false)
    await act(() => window.dispatchEvent(new Event('offline')))
    await tick(4_000)
    expect(onRead).not.toHaveBeenCalled()
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(true)
    await act(() => window.dispatchEvent(new Event('online')))
    await tick(2_999)
    expect(onRead).not.toHaveBeenCalled()
    await tick(1)
    expect(onRead).toHaveBeenCalledExactlyOnceWith('sue-4')
  })
})
