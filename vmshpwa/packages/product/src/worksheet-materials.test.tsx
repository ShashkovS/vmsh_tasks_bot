import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { WorksheetMaterials } from './worksheet-materials'
import { renderWithI18n as render } from '@vmsh/test-utils/i18n'
afterEach(cleanup)
const unavailable = { available: false, load: () => Promise.resolve(null) }
it('does not load before confirmation or after cancellation, then reopens without a request', async () => {
  const load = vi.fn().mockResolvedValue(<p>Текст подсказки</p>)
  render(
    <WorksheetMaterials
      hint={{ available: true, confirmationRequired: true, load }}
      solution={unavailable}
    />,
  )
  fireEvent.click(screen.getByRole('button', { name: 'Подсказка' }))
  expect(load).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Отмена' }))
  expect(load).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Подсказка' }))
  fireEvent.click(screen.getByRole('button', { name: 'Показать подсказку' }))
  await screen.findByText('Текст подсказки')
  fireEvent.click(screen.getByRole('button', { name: 'Скрыть подсказку' }))
  fireEvent.click(screen.getByRole('button', { name: 'Подсказка' }))
  expect(screen.queryByRole('button', { name: 'Показать подсказку' })).toBeNull()
  expect(load).toHaveBeenCalledOnce()
})
it('loads a new publication without another confirmation and leaves revisits collapsed', async () => {
  const load = vi.fn().mockResolvedValue(<p>Новая версия</p>)
  const view = render(
    <WorksheetMaterials
      hint={{ available: true, confirmationRequired: false, load }}
      solution={unavailable}
    />,
  )
  expect(load).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Подсказка' }))
  await screen.findByText('Новая версия')
  view.unmount()
  render(
    <WorksheetMaterials
      hint={{ available: true, confirmationRequired: false, load }}
      solution={unavailable}
    />,
  )
  expect(screen.queryByText('Новая версия')).toBeNull()
})
it('retries a failed solution without confirmation or showing failed content', async () => {
  const load = vi
    .fn()
    .mockRejectedValueOnce(new Error('network'))
    .mockResolvedValue(<p>Решение задачи</p>)
  render(<WorksheetMaterials hint={unavailable} solution={{ available: true, load }} />)
  fireEvent.click(screen.getByRole('button', { name: 'Решение' }))
  await screen.findByRole('alert')
  fireEvent.click(screen.getByRole('button', { name: 'Повторить' }))
  await screen.findByText('Решение задачи')
  expect(load).toHaveBeenCalledTimes(2)
  await waitFor(() => expect(screen.queryByRole('alert')).toBeNull())
})
it('previews loaded material without loading or recording a student view', () => {
  const load = vi.fn()
  render(
    <WorksheetMaterials
      defaultOpen="hint"
      hint={{ available: true, load, preview: <p>Превью</p> }}
      solution={unavailable}
    />,
  )
  expect(screen.getByText('Превью')).toBeTruthy()
  expect(load).not.toHaveBeenCalled()
})
