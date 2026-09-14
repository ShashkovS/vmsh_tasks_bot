import { act, cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { LiveMarkButton, type MarkDisplay } from './live-marking-grid'

afterEach(() => {
  cleanup()
  vi.useRealTimers()
})
const saved: MarkDisplay = { symbol: '+', mine: true, changed: false, disabled: false }
function button(display: MarkDisplay) {
  return (
    <LiveMarkButton
      label="Ученик, задача 1н.1"
      display={display}
      studentId="u-1"
      problemId="p-1"
      onMark={() => {}}
    />
  )
}
it('never displays a pending plus; escalates one second after sending and clears on receipt', () => {
  vi.useFakeTimers()
  const { rerender } = render(button({ ...saved, pending: 'draft' }))
  const cell = screen.getByRole('button')
  expect(cell.textContent).not.toContain('+')
  expect(cell.getAttribute('aria-label')).toContain('Ожидает отправки')
  void act(() => vi.advanceTimersByTime(2000))
  rerender(button({ ...saved, pending: 'sending' }))
  void act(() => vi.advanceTimersByTime(999))
  expect(cell.textContent).not.toContain('…')
  void act(() => vi.advanceTimersByTime(1))
  expect(cell.textContent).toContain('…')
  expect(cell.getAttribute('aria-label')).toContain('Сохранение не подтверждено')
  rerender(button(saved))
  expect(cell.textContent).toContain('+')
  expect(cell.textContent).not.toContain('…')
  expect(cell.getAttribute('aria-label')).toContain('Сохранено')
})
it.each(['queued', 'failed', 'conflict'] as const)(
  'keeps %s distinct from a saved mark',
  (pending) => {
    render(button({ ...saved, pending }))
    expect(screen.getByRole('button').textContent).not.toContain('+')
    expect(screen.getByRole('button').textContent).toContain('…')
  },
)
it('does not retain slow state for another send', () => {
  vi.useFakeTimers()
  const { rerender } = render(button({ ...saved, pending: 'sending' }))
  void act(() => vi.advanceTimersByTime(1000))
  rerender(button(saved))
  rerender(button({ ...saved, pending: 'sending' }))
  expect(screen.getByRole('button').textContent).not.toContain('…')
})
