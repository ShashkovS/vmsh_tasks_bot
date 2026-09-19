import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { FamilyLoginPage } from './pages'

afterEach(() => cleanup())

describe('Family login page', () => {
  it('submits the separate family password contract', async () => {
    const onSubmit = vi.fn()
    render(<FamilyLoginPage onSubmit={onSubmit} />)

    fireEvent.change(screen.getByLabelText('Логин'), { target: { value: 'family-login' } })
    fireEvent.change(screen.getByLabelText('Пароль'), {
      target: { value: 'synthetic-password' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Войти' }))

    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith({
        username: 'family-login',
        password: 'synthetic-password',
      }),
    )
    expect(onSubmit.mock.calls[0]?.[0]).not.toHaveProperty('telegramToken')
  })

  it('keeps the legacy invalid prop and password reveal story behavior', () => {
    render(<FamilyLoginPage invalid />)
    expect(screen.getByRole('alert').textContent).toContain('Логин или пароль не подошли')
    fireEvent.click(screen.getByRole('button', { name: 'Показать пароль' }))
    expect(screen.getByLabelText('Пароль').getAttribute('type')).toBe('text')
  })
})
