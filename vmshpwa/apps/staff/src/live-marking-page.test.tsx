import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import type { LiveDirectoryStudent } from '@vmsh/contracts'

import { StudentSearch } from './live-marking-page'

const students = [
  {
    studentId: 'u-1',
    displayName: 'Абрамов Герман',
    surname: 'Абрамов',
    middleName: 'Сергеевич',
    grade: 5,
    groupId: 'g-1',
    groupName: 'Начинающие',
    attendanceMode: 'online',
    enrollmentVersion: 1,
    rooms: [],
  },
  {
    studentId: 'u-2',
    displayName: 'Сергеев Фёдор',
    surname: 'Сергеев',
    middleName: 'Николаевич',
    grade: 6,
    groupId: 'g-1',
    groupName: 'Начинающие',
    attendanceMode: 'in_person',
    enrollmentVersion: 1,
    rooms: [],
  },
  {
    studentId: 'u-3',
    displayName: 'Де ла Крус Анна',
    surname: 'Де ла Крус',
    middleName: 'Сергеевна',
    grade: 7,
    groupId: 'g-2',
    groupName: 'Продолжающие',
    attendanceMode: 'online',
    enrollmentVersion: 1,
    rooms: [],
  },
] satisfies LiveDirectoryStudent[]

function SearchHarness() {
  const [surnameOnly, setSurnameOnly] = useState(false)
  const [searchNumber, setSearchNumber] = useState(1)
  return (
    <>
      <button type="button" onClick={() => setSearchNumber((value) => value + 1)}>
        Следующий поиск
      </button>
      <StudentSearch
        key={searchNumber}
        students={students}
        onSelect={vi.fn()}
        transfer={false}
        surnameOnly={surnameOnly}
        onSurnameOnlyChange={setSurnameOnly}
      />
    </>
  )
}

describe('live marking student search', () => {
  beforeAll(() => {
    Object.defineProperty(window, 'PointerEvent', { configurable: true, value: MouseEvent })
  })
  afterEach(() => cleanup())

  it('searches by surname and name without matching a patronymic', async () => {
    const user = userEvent.setup()
    render(<SearchHarness />)

    const search = screen.getByRole('searchbox', { name: 'Поиск школьника' })
    await user.type(search, 'сергеев')

    screen.getByText('Сергеев Фёдор')
    expect(screen.queryByText('Абрамов Герман')).toBeNull()
    expect(screen.queryByText('Де ла Крус Анна')).toBeNull()

    await user.clear(search)
    await user.type(search, 'герман')
    screen.getByText('Абрамов Герман')
  })

  it('limits matching to the explicit surname and remembers the mode between searches', async () => {
    const user = userEvent.setup()
    render(<SearchHarness />)

    const surnameOnly = screen.getByRole('switch', { name: 'Искать только по фамилии' })
    await user.click(surnameOnly)
    expect(surnameOnly.getAttribute('aria-checked')).toBe('true')
    screen.getByPlaceholderText('Фамилия…')

    const search = screen.getByRole('searchbox', { name: 'Поиск школьника' })
    await user.type(search, 'герман')
    expect(screen.queryByText('Абрамов Герман')).toBeNull()
    screen.getByText('Никого не нашли. Попробуйте другую часть фамилии.')

    await user.clear(search)
    await user.type(search, 'сергеевв')
    screen.getByText('Сергеев Фёдор')

    await user.clear(search)
    await user.type(search, 'ла крус')
    screen.getByText('Де ла Крус Анна')

    await user.click(screen.getByRole('button', { name: 'Следующий поиск' }))
    expect(
      screen.getByRole('switch', { name: 'Искать только по фамилии' }).getAttribute('aria-checked'),
    ).toBe('true')
    screen.getByText('Введите фамилию школьника.')
  })
})
