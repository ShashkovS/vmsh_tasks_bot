import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { StatisticsStudentSearch } from './statistics-student-search'

afterEach(cleanup)

it('searches with typos, mixed case, ё and reversed name order without selecting on input', () => {
  const onChange = vi.fn()
  render(
    <StatisticsStudentSearch
      students={[{ studentId: 'u-1', name: 'Шаманин Пётр' }]}
      studentId={null}
      onChange={onChange}
    />,
  )
  fireEvent.change(screen.getByLabelText('График школьника'), {
    target: { value: 'ПЕТР шаманинн' },
  })
  expect(onChange).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Шаманин Пётр' }))
  expect(onChange).toHaveBeenCalledWith('u-1')
})

it('bounds results for 2000 students, preserves selection and supports empty results and clearing', () => {
  const onChange = vi.fn()
  render(
    <StatisticsStudentSearch
      students={Array.from({ length: 2000 }, (_, i) => ({
        studentId: `u-${i}`,
        name: `Ученик ${i}`,
      }))}
      studentId="u-1999"
      onChange={onChange}
    />,
  )
  expect(screen.getByText('Выбран: Ученик 1999')).toBeTruthy()
  expect(screen.queryAllByRole('listitem')).toHaveLength(0)
  fireEvent.change(screen.getByLabelText('График школьника'), { target: { value: 'Ученик' } })
  expect(screen.getAllByRole('listitem')).toHaveLength(20)
  expect(screen.getByRole('status').textContent).toContain('2000')
  fireEvent.change(screen.getByLabelText('График школьника'), {
    target: { value: 'Несуществующий' },
  })
  expect(screen.getByText('Школьники не найдены')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'Сбросить выбор' }))
  expect(onChange).toHaveBeenCalledWith(null)
})
