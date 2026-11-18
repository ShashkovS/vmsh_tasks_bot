import { cleanup, fireEvent, screen } from '@testing-library/react'
import { renderWithI18n as render } from '@vmsh/test-utils/i18n'
import { afterEach, expect, it } from 'vitest'
import { LessonBlocksLayout } from './lesson-blocks'
import { parseLessonRichMarkdown } from './lesson-rich-markdown'

afterEach(cleanup)
it('renders separate paper sections and activates the normalized player on click', () => {
  const { container } = render(
    <LessonBlocksLayout
      before={parseLessonRichMarkdown('Перед')}
      after={parseLessonRichMarkdown('После\n\n::video[](https://youtu.be/4ke2IJirSds)\n')}
      idPrefix="test"
    >
      <div data-testid="tasks">Задачи</div>
    </LessonBlocksLayout>,
  )
  expect([...container.children].map((el) => el.textContent)).toEqual([
    'Перед',
    'Задачи',
    expect.stringContaining('После'),
  ])
  expect(container.querySelectorAll('.vmsh-lesson-block')).toHaveLength(2)
  expect(container.querySelector('iframe')).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'Загрузить видео' }))
  expect(container.querySelector('iframe')?.getAttribute('src')).toBe(
    'https://www.youtube.com/embed/4ke2IJirSds?start=0',
  )
  expect(container.querySelector('iframe')?.getAttribute('referrerpolicy')).toBe(
    'strict-origin-when-cross-origin',
  )
})
