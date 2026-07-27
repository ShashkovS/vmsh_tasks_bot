import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { StudentLoginPage } from './pages'

afterEach(() => cleanup())

describe('Student login page', () => {
  it('submits the Telegram token contract and never a generic password field', async () => {
    const onSubmit = vi.fn()
    render(<StudentLoginPage onSubmit={onSubmit} />)

    expect(screen.getByRole('button', { name: 'Войти' }).hasAttribute('disabled')).toBe(true)
    fireEvent.change(screen.getByLabelText('Логин'), { target: { value: 'petrov-14' } })
    fireEvent.change(screen.getByLabelText('Токен Telegram-бота'), {
      target: { value: 'synthetic-token' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Войти' }))

    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith({
        username: 'petrov-14',
        telegramToken: 'synthetic-token',
      }),
    )
    expect(onSubmit.mock.calls[0]?.[0]).not.toHaveProperty('password')
  })

  it('shows a non-enumerating unavailable state and locks a pending form', () => {
    const { rerender } = render(<StudentLoginPage loginState="account-unavailable" />)
    expect(screen.getByRole('alert').textContent).toContain('учётной записи сейчас недоступен')

    rerender(<StudentLoginPage loginState="pending" />)
    expect(screen.getByRole('button', { name: 'Входим…' }).hasAttribute('disabled')).toBe(true)
    expect(screen.getByLabelText('Логин').hasAttribute('disabled')).toBe(true)
    expect(screen.getByLabelText('Токен Telegram-бота').hasAttribute('disabled')).toBe(true)
  })
})
