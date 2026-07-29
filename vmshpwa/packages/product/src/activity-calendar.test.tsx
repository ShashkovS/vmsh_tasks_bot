import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { ActivityCalendar } from './activity-calendar'

afterEach(() => cleanup())

describe('personal activity calendar', () => {
  it('shows only the learner activity and an accessible date list', () => {
    render(
      <ActivityCalendar
        days={[
          { date: '2026-01-12', problemCount: 1 },
          { date: '2026-01-15', problemCount: 3 },
        ]}
      />,
    )

    expect(screen.getByText('2 дня работы · 4 задачи')).toBeTruthy()
    fireEvent.click(screen.getByText('Показать по датам'))
    expect(screen.getByText(/12 янв/)).toBeTruthy()
    expect(screen.getByText(/15 янв/)).toBeTruthy()
    expect(screen.queryByText(/группа|рейтинг|процентиль/i)).toBeNull()
  })
})
