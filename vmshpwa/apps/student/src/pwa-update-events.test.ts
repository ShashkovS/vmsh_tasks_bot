import { describe, expect, it, vi } from 'vitest'

import { announceSafePwaUpdateMoment, safePwaUpdateEvent } from './pwa-update-events'

describe('safe PWA update moments', () => {
  it('announces that a confirmed operation no longer blocks an update', () => {
    const listener = vi.fn()
    window.addEventListener(safePwaUpdateEvent, listener, { once: true })

    announceSafePwaUpdateMoment()

    expect(listener).toHaveBeenCalledOnce()
  })
})
