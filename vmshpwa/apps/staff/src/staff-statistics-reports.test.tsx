import { cleanup, screen } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import { renderWithI18n as render } from '@vmsh/test-utils/i18n'
import { statisticsPlusTableSchema } from '@vmsh/contracts'
import { PlusMatrix } from './staff-statistics-reports'

afterEach(cleanup)
it('renders all rows, partial credit, channel and pending alongside credit', () => {
  const data = statisticsPlusTableSchema.parse({
    schemaVersion: 1,
    courses: [],
    selectedCourseId: null,
    selectedGroupId: null,
    requestId: 'test',
    lessonNumbers: [0],
    lessonNumber: 0,
    problems: [{ problemId: 'p-1', label: '1а', title: 'Задача' }],
    rows: [
      {
        studentId: 'u-1',
        name: 'Иванов Иван',
        total: 0.5,
        cells: [{ score: 0.5, source: 'written', attempted: true, pending: true }],
      },
    ],
  })
  render(<PlusMatrix data={data} />)
  expect(screen.getByRole('rowheader', { name: 'Иванов Иван' })).toBeTruthy()
  expect(screen.getByRole('cell', { name: /1а · ½ · Письменно · Ожидает проверки/ })).toBeTruthy()
  expect(screen.getByText('½…')).toBeTruthy()
})
