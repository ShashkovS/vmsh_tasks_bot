import { act, cleanup, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from 'vitest'

import { rememberWorksheet, useWorksheetReturn } from './worksheet-return'

// docs/task-interaction-polish.md: browser history must not replace the exact
// task offset; explicit user scrolling takes over immediately.
describe('worksheet return after browser history scroll', () => {
  let scrollY: number
  let taskY: number
  let frames: Map<number, FrameRequestCallback>
  let nextFrame: number
  let resize: () => void
  let scrollBy: Mock<(options: ScrollToOptions | number) => void>

  function flushFrames() {
    act(() => {
      const callbacks = [...frames.values()]
      frames.clear()
      for (const callback of callbacks) callback(0)
    })
  }

  beforeEach(() => {
    vi.useFakeTimers()
    scrollY = 250
    taskY = 400
    frames = new Map()
    nextFrame = 0
    vi.stubGlobal('CSS', { escape: (value: string) => value })
    window.history.replaceState({ __TSR_index: 1 }, '', '/tasks/')
    const anchor = document.createElement('button')
    anchor.dataset.taskReturnId = 'p-return-test'
    anchor.getBoundingClientRect = () => new DOMRect(0, taskY - scrollY, 100, 40)
    document.body.append(anchor)
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((callback) => {
      frames.set(++nextFrame, callback)
      return nextFrame
    })
    vi.spyOn(window, 'cancelAnimationFrame').mockImplementation((id) => frames.delete(id))
    scrollBy = vi.fn((options: ScrollToOptions | number) => {
      if (typeof options === 'object') scrollY += options.top ?? 0
    })
    vi.stubGlobal('scrollBy', scrollBy)
    vi.stubGlobal(
      'ResizeObserver',
      class {
        constructor(callback: () => void) {
          resize = callback
        }
        observe() {}
        disconnect() {}
      },
    )
    rememberWorksheet('p-return-test')
    scrollY = 0
  })

  afterEach(() => {
    cleanup()
    document.body.replaceChildren()
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
    vi.useRealTimers()
  })

  it('keeps the task offset when native history resets scroll after layout', () => {
    renderHook(() => useWorksheetReturn())
    flushFrames()
    expect(scrollY).toBe(250)
    scrollY = 0
    window.dispatchEvent(new Event('scroll'))
    flushFrames()
    expect(scrollY).toBe(250)
    // Late figures can move the task while the archive finishes rendering.
    taskY += 100
    resize()
    flushFrames()
    expect(taskY - scrollY).toBe(150)
    window.dispatchEvent(new Event('scroll'))
    flushFrames()
    expect(frames.size).toBe(0)
    expect(scrollBy).toHaveBeenCalledTimes(3)
  })

  it('lets user input take over without pulling the worksheet back', () => {
    renderHook(() => useWorksheetReturn())
    flushFrames()
    window.dispatchEvent(new Event('wheel'))
    scrollY = 100
    window.dispatchEvent(new Event('scroll'))
    resize()
    flushFrames()
    expect(scrollY).toBe(100)
    expect(scrollBy).toHaveBeenCalledTimes(1)
  })

  it('stops observing after unmount and after the restoration window', () => {
    const hook = renderHook(() => useWorksheetReturn())
    flushFrames()
    hook.unmount()
    scrollY = 0
    window.dispatchEvent(new Event('scroll'))
    flushFrames()
    expect(scrollY).toBe(0)
    renderHook(() => useWorksheetReturn())
    flushFrames()
    expect(scrollY).toBe(250)
    act(() => {
      vi.advanceTimersByTime(5_000)
    })
    scrollY = 100
    window.dispatchEvent(new Event('scroll'))
    flushFrames()
    expect(scrollY).toBe(100)
  })
})
