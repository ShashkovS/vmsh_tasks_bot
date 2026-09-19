import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'

import type { StudentOralWindow } from '@vmsh/contracts'
import { OralAdmission } from './oral-admission'

const window: StudentOralWindow = {
  windowId: 'ow-1',
  sequenceNumber: 1,
  opensAt: '2026-10-05T11:00:00Z',
  closesAt: '2026-10-05T13:00:00Z',
  joinLabel: 'Подключиться к Zoom',
  state: 'upcoming',
  joinAvailable: false,
  version: 1,
}
afterEach(cleanup)

it('renders nothing for empty, completed or cancelled schedules', () => {
  const { container, rerender } = render(<OralAdmission windows={[]} />)
  expect(container.innerHTML).toBe('')
  rerender(
    <OralAdmission
      windows={[
        { ...window, state: 'closed' },
        { ...window, windowId: 'ow-2', state: 'cancelled' },
      ]}
    />,
  )
  expect(container.innerHTML).toBe('')
})

it('shows future time without the large heading, cards or unavailable join action', () => {
  render(<OralAdmission windows={[window, { ...window, windowId: 'ow-2', state: 'closed' }]} />)
  expect(screen.getByRole('region', { name: 'Устный приём' })).toBeTruthy()
  expect(screen.queryByRole('heading')).toBeNull()
  expect(screen.queryByRole('button')).toBeNull()
  expect(screen.queryByText('Завершено')).toBeNull()
  expect(screen.queryByText('Окно 1')).toBeNull()
})

it('reveals join details only for an open window and removes stale secrets when closed', async () => {
  const reveal = vi.fn()
  const open = { ...window, state: 'open' as const, joinAvailable: true }
  const { rerender, container } = render(<OralAdmission windows={[open]} onRevealJoin={reveal} />)
  await userEvent.click(screen.getByRole('button', { name: window.joinLabel }))
  expect(reveal).toHaveBeenCalledWith('ow-1')
  const join = {
    windowId: 'ow-1',
    joinUrl: 'https://zoom.example.test/j/1',
    joinLabel: 'Открыть Zoom',
    joinCode: '123',
    closesAt: window.closesAt,
  }
  rerender(<OralAdmission windows={[open]} revealedJoin={join} />)
  expect(screen.getByRole('link', { name: /Открыть Zoom/ }).getAttribute('href')).toBe(join.joinUrl)
  rerender(<OralAdmission windows={[{ ...open, state: 'closed' }]} revealedJoin={join} />)
  expect(container.innerHTML).toBe('')
})
