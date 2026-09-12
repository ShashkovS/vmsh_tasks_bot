import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { StaffLoginPage } from './pages'

afterEach(() => cleanup())

describe('Staff login page', () => {
  it('submits the staff password contract and exposes the support address', async () => {
    const onSubmit = vi.fn()
    render(<StaffLoginPage onSubmit={onSubmit} />)

    fireEvent.change(screen.getByLabelText('Логин'), { target: { value: 'teacher-login' } })
    fireEvent.change(screen.getByLabelText('Пароль'), {
      target: { value: 'synthetic-password' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Войти' }))

    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith({
        username: 'teacher-login',
        password: 'synthetic-password',
      }),
    )
    expect(screen.getByRole('link', { name: 'vmsh@179.ru' }).getAttribute('href')).toBe(
      'mailto:vmsh@179.ru',
    )
  })

  it('supports password reveal and a locked pending state', () => {
    const { rerender } = render(<StaffLoginPage />)
    fireEvent.click(screen.getByRole('button', { name: 'Показать пароль' }))
    expect(screen.getByLabelText('Пароль').getAttribute('type')).toBe('text')

    rerender(<StaffLoginPage loginState="pending" />)
    expect(screen.getByRole('button', { name: 'Входим…' }).hasAttribute('disabled')).toBe(true)
  })
})
