import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import type { SupportClient } from './support-client'
import { PhotoSupportComposer } from './photo-support-composer'
import { renderWithI18n as render } from '@vmsh/test-utils/i18n'

const state = vi.hoisted(() => ({
  clear: vi.fn<() => Promise<void>>().mockResolvedValue(undefined),
  namespace: vi.fn(),
}))
vi.mock('./auth-context', () => ({
  useAuthenticatedPrincipal: () => ({ audience: 'staff', accountId: 'a-42' }),
  useAuthentication: () => ({ client: { runtime: { instance: 'test' } } }),
}))
vi.mock('@vmsh/offline', async () => {
  const { useState } = await import('react')
  return {
    useOrganizerDraft: (namespace: string, key: string) => {
      state.namespace(namespace, key)
      const [draft, update] = useState({ photos: [] as Blob[], uploadedIds: [] as string[] })
      return { draft, update, ready: true, saved: true, unavailable: false, clear: state.clear }
    },
  }
})
beforeEach(() => {
  vi.stubGlobal(
    'URL',
    Object.assign(URL, {
      createObjectURL: vi.fn(() => 'blob:photo'),
      revokeObjectURL: vi.fn(),
    }),
  )
})
afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  vi.unstubAllGlobals()
})

it('keeps uploaded photos after failure and reuses them for a photo-only reply', async () => {
  const uploadPhoto = vi
    .fn<NonNullable<SupportClient['uploadPhoto']>>()
    .mockResolvedValue('sup-123')
  const submit = vi
    .fn<(ids: string[], clear: () => Promise<void>) => Promise<void>>()
    .mockRejectedValueOnce(new Error('offline'))
    .mockImplementationOnce(async (_ids, clear) => clear())
  render(
    <PhotoSupportComposer
      client={{ uploadPhoto }}
      photoDraftKey="thread:sup-177"
      allowPhotoOnly
      value=""
      onValueChange={() => {}}
      onSubmit={submit}
      submitLabel="Ответить"
    />,
  )
  const send = screen.getByRole<HTMLButtonElement>('button', { name: 'Ответить' })
  expect(send.disabled).toBe(true)
  fireEvent.change(screen.getByLabelText('Выбрать фотографии', { selector: 'input' }), {
    target: { files: [new File(['image'], 'answer.png', { type: 'image/png' })] },
  })
  expect(send.disabled).toBe(false)
  fireEvent.click(send)
  await screen.findByRole('alert')
  expect(screen.getByAltText('Выбранная фотография')).toBeTruthy()
  expect(state.clear).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Ответить' }))
  await waitFor(() => expect(state.clear).toHaveBeenCalledOnce())
  expect(uploadPhoto).toHaveBeenCalledOnce()
  expect(submit.mock.calls.map(([ids]) => ids)).toEqual([['sup-123'], ['sup-123']])
  expect(state.namespace).toHaveBeenCalledWith('test:staff:a-42:support', 'thread:sup-177')
})

it('removing the only photo disables an empty reply again', () => {
  render(
    <PhotoSupportComposer
      client={{}}
      photoDraftKey="thread:sup-2"
      allowPhotoOnly
      value=""
      onValueChange={() => {}}
      onSubmit={vi.fn()}
    />,
  )
  fireEvent.change(screen.getByLabelText('Выбрать фотографии', { selector: 'input' }), {
    target: { files: [new File(['image'], 'answer.png', { type: 'image/png' })] },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Убрать фотографию 1' }))
  expect(screen.getByRole<HTMLButtonElement>('button', { name: 'Отправить' }).disabled).toBe(true)
})
