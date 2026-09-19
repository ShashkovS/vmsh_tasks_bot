import { act, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { NotificationEvent } from '@vmsh/contracts'

import { VisibleNotification } from './student-notifications-page'

const event: NotificationEvent = {
  eventId: 'notification.classroom-41',
  category: 'classroom_assignment',
  route: '/student/',
  payload: { classroomName: '202' },
  occurredAt: '2026-10-05T12:00:00Z',
  deliverAfter: '2026-10-05T12:00:00Z',
  readAt: null,
}

function installIntersectionObserver() {
  let notify: IntersectionObserverCallback = () => undefined
  class FakeIntersectionObserver implements IntersectionObserver {
    readonly root = null
    readonly rootMargin = '0px'
    readonly scrollMargin = '0px'
    readonly thresholds = [0.75]
    constructor(callback: IntersectionObserverCallback) {
      notify = callback
    }
    disconnect() {}
    observe() {}
    takeRecords() {
      return []
    }
    unobserve() {}
  }
  vi.stubGlobal('IntersectionObserver', FakeIntersectionObserver)
  return (visible: boolean) =>
    notify(
      [
        {
          isIntersecting: visible,
          intersectionRatio: visible ? 0.8 : 0,
        } as IntersectionObserverEntry,
      ],
      {} as IntersectionObserver,
    )
}

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('notification visibility acknowledgement', () => {
  it('shows the number of reviews collected in one batch', () => {
    installIntersectionObserver()
    render(
      <VisibleNotification
        event={{
          ...event,
          category: 'review_completed',
          payload: { count: 3 },
        }}
        onRead={vi.fn()}
      />,
    )

    expect(screen.getByText('Проверено задач: 3')).toBeTruthy()
  })

  it('acknowledges only after three continuous visible seconds', () => {
    vi.useFakeTimers()
    const setVisible = installIntersectionObserver()
    const onRead = vi.fn()
    render(<VisibleNotification event={event} onRead={onRead} />)

    act(() => {
      setVisible(true)
    })
    act(() => {
      vi.advanceTimersByTime(2_999)
    })
    expect(onRead).not.toHaveBeenCalled()
    act(() => {
      vi.advanceTimersByTime(1)
    })
    expect(onRead).toHaveBeenCalledExactlyOnceWith(event.eventId)
  })

  it('restarts the timer after the item leaves the viewport', () => {
    vi.useFakeTimers()
    const setVisible = installIntersectionObserver()
    const onRead = vi.fn()
    render(<VisibleNotification event={event} onRead={onRead} />)

    act(() => {
      setVisible(true)
    })
    act(() => {
      vi.advanceTimersByTime(2_000)
    })
    act(() => {
      setVisible(false)
    })
    act(() => {
      vi.advanceTimersByTime(2_000)
    })
    expect(onRead).not.toHaveBeenCalled()
    act(() => {
      setVisible(true)
    })
    act(() => {
      vi.advanceTimersByTime(3_000)
    })
    expect(onRead).toHaveBeenCalledOnce()
  })
})
