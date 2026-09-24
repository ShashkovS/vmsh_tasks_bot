import { cleanup, fireEvent, screen } from '@testing-library/react'
import { renderWithI18n as render } from '@vmsh/test-utils/i18n'
import { afterEach, expect, it, vi } from 'vitest'
import { LessonVideoDialog } from './lesson-video-dialog'
import { parseLessonRichMarkdown } from '@vmsh/product'

afterEach(cleanup)

it.each([
  ['https://youtu.be/4ke2IJirSds', 'youtube'],
  ['<iframe src="https://www.youtube.com/embed/4ke2IJirSds" allowfullscreen></iframe>', 'youtube'],
  [
    '<iframe src="https://vkvideo.ru/video_ext.php?oid=-241691838&amp;id=456239017&amp;hd=2" allowfullscreen></iframe>',
    'vk',
  ],
])('inserts %s as a playable document node', (source, provider) => {
  const onInsert = vi.fn()
  render(<LessonVideoDialog onInsert={onInsert} />)
  fireEvent.click(screen.getByText('Добавить видео'))
  fireEvent.change(screen.getByLabelText('Ссылка YouTube/VK или iframe'), {
    target: { value: source },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Вставить видео' }))
  expect(onInsert).toHaveBeenCalledOnce()
  expect(parseLessonRichMarkdown(`Описание${onInsert.mock.calls[0]?.[0]}`).blocks).toContainEqual(
    expect.objectContaining({ type: 'video', provider }),
  )
})
