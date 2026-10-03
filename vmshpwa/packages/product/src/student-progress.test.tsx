import { i18n } from '@lingui/core'
import { cleanup, screen } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import { renderWithI18n } from '@vmsh/test-utils/i18n'
import { StudentProgress } from './student-progress'

afterEach(cleanup)

// P8: English plural selection must not follow Russian last-digit rules.
it.each([1, 2, 5, 11, 21])('renders English progress for %i accepted problems', (count) => {
  i18n.activate('en')
  renderWithI18n(
    <StudentProgress solvedCount={count} attemptedCount={30} achievements={['Авторский текст']} />,
  )
  expect(
    screen.getByText(count === 1 ? 'problem accepted' : 'problems accepted', { exact: false }),
  ).toBeTruthy()
  expect(screen.getByText('Авторский текст')).toBeTruthy()
})
