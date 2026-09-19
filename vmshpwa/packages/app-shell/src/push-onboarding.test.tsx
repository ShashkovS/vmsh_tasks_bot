import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import type { NotificationClient } from './notification-client'
import { PushInvitation } from './push-onboarding'

const push = vi.hoisted(() => ({
  state: 'available',
  enable: vi.fn(),
  disable: vi.fn(),
  dismiss: vi.fn(),
}))
vi.mock('./push-device', () => ({ usePushDevice: () => push }))
const props = {
  client: {} as NotificationClient,
  applicationServerKey: 'public',
  storageKey: 'student:one',
  audience: 'student' as const,
}
beforeEach(() => {
  const values = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => values.get(key),
    setItem: (key: string, value: string) => values.set(key, value),
    clear: () => values.clear(),
  })
})
afterEach(() => {
  cleanup()
  localStorage.clear()
  push.state = 'available'
  vi.clearAllMocks()
})
it('requests consent only on click and remembers account-scoped dismissal', () => {
  const view = render(<PushInvitation {...props} />)
  expect(push.enable).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Включить уведомления' }))
  expect(push.enable).toHaveBeenCalledOnce()
  fireEvent.click(screen.getByRole('button', { name: 'Не сейчас' }))
  view.unmount()
  const second = render(<PushInvitation {...props} />)
  expect(screen.queryByRole('region')).toBeNull()
  second.unmount()
  render(<PushInvitation {...props} storageKey="family:two" audience="family" />)
  expect(screen.getByRole('button', { name: 'Включить уведомления' })).toBeTruthy()
})
it('explains iOS installation without offering an unavailable permission action', () => {
  push.state = 'install-required'
  render(<PushInvitation {...props} />)
  expect(screen.getByText(/Добавьте кабинет на экран/)).toBeTruthy()
  expect(screen.queryByRole('button', { name: 'Включить уведомления' })).toBeNull()
})
it('prevents duplicate consent while enabling and offers retry after failure', () => {
  push.state = 'enabling'
  const view = render(<PushInvitation {...props} />)
  expect(screen.getByRole('button', { name: 'Включаем…' }).hasAttribute('disabled')).toBe(true)
  push.state = 'error'
  view.rerender(<PushInvitation {...props} />)
  fireEvent.click(screen.getByRole('button', { name: 'Включить уведомления' }))
  expect(push.enable).toHaveBeenCalledOnce()
})
