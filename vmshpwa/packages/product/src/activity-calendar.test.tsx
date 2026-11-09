import { cleanup, fireEvent, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { activateLocale } from '@vmsh/i18n'
import { allCatalogLoaders } from '../../../dev/test-support/i18n-catalogs'
import { ActivityCalendar } from './activity-calendar'
import { renderWithI18n as render } from '@vmsh/test-utils/i18n'

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

  it('uses the active English locale for plural labels and dates', async () => {
    await activateLocale('en', allCatalogLoaders)
    render(
      <ActivityCalendar
        days={[
          { date: '2026-01-12', problemCount: 1 },
          { date: '2026-01-15', problemCount: 3 },
        ]}
      />,
    )

    expect(screen.getByText('2 active days · 4 problems')).toBeTruthy()
    fireEvent.click(screen.getByText('Show by date'))
    expect(screen.getByText(/Jan 12/)).toBeTruthy()
    expect(screen.getByText(/Jan 15/)).toBeTruthy()
  })
})
