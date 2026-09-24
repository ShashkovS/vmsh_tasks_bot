import { cleanup, fireEvent, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { TestAttemptRecheckPanel } from './test-attempt-recheck'
import { renderWithI18n as render } from '@vmsh/test-utils/i18n'

afterEach(() => cleanup())

describe('TestAttemptRecheckPanel', () => {
  it('shows the exact preview and requires one explicit action', () => {
    const onApply = vi.fn()
    render(
      <TestAttemptRecheckPanel
        becameCorrect={2}
        becameWrong={1}
        formatChanges={1}
        invalidFormat={1}
        messageChanges={3}
        onApply={onApply}
        pendingAttempts={3}
        problem={{ displayNumber: '1н.6', title: 'Числа в ряд', correctAnswer: '29' }}
        studentCount={1}
        updatesRequired={3}
        verdictChanges={3}
      />,
    )

    expect(screen.getByText(/Задача 1н\.6/).textContent).toContain('Числа в ряд')
    expect(screen.getByText('Текущий правильный ответ: 29')).toBeTruthy()
    expect(screen.getByText('− → +').parentElement?.textContent).toContain('2')
    expect(screen.getByText('+ → −').parentElement?.textContent).toContain('1')

    fireEvent.click(screen.getByRole('button', { name: 'Перепроверить все 3 ответа' }))
    expect(onApply).toHaveBeenCalledOnce()
  })

  it('reports applied, unchanged and unresolved attempts separately', () => {
    render(
      <TestAttemptRecheckPanel
        pendingAttempts={3}
        result={{
          pendingBefore: 3,
          checked: 1,
          correct: 1,
          wrong: 0,
          stillPending: 1,
          skippedConcurrent: 0,
          scannedAttempts: 3,
          updatedAttempts: 2,
          unchangedAttempts: 1,
          verdictChanges: 1,
          becameCorrect: 1,
          becameWrong: 0,
          formatChanges: 1,
          invalidFormat: 1,
          pendingConfiguration: 1,
          checkerFailed: 0,
          messageChanges: 2,
        }}
      />,
    )

    expect(screen.getByText('Проверено 3, обновлено 2')).toBeTruthy()
    expect(screen.getByText(/Без изменений: 1/)).toBeTruthy()
    expect(screen.getByText(/ожидают настройки: 1/)).toBeTruthy()
  })
})
