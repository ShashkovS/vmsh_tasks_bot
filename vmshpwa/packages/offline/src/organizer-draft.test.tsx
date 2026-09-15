import 'fake-indexeddb/auto'
import { act, renderHook, waitFor } from '@testing-library/react'
import { expect, it } from 'vitest'
import { useOrganizerDraft } from './organizer-draft'
it('preserves photo draft and upload identities across reload, isolates family and clears confirmed send', async () => {
  const name = `unit-${crypto.randomUUID()}`
  const first = renderHook(() => useOrganizerDraft(`${name}:student:a-1`, 'new'))
  await waitFor(() => expect(first.result.current.ready).toBe(true))
  const original = first.result.current.draft
  const photo = new Blob(['photo'], { type: 'image/webp' })
  // jsdom omits Blob.arrayBuffer; browsers exercise the native method in E2E.
  Object.defineProperty(photo, 'arrayBuffer', {
    value: () => Promise.resolve(new TextEncoder().encode('photo').buffer),
  })
  act(() =>
    first.result.current.update({
      ...original,
      text: 'Вопрос',
      photos: [photo],
      uploadedIds: ['oqp-1'],
    }),
  )
  await waitFor(() => expect(first.result.current.saved).toBe(true))
  first.unmount()
  const restored = renderHook(() => useOrganizerDraft(`${name}:student:a-1`, 'new'))
  await waitFor(() => expect(restored.result.current.ready).toBe(true))
  expect(restored.result.current.draft.text).toBe('Вопрос')
  expect(restored.result.current.draft.photos).toHaveLength(1)
  expect(restored.result.current.draft.uploadedIds).toEqual(['oqp-1'])
  expect(restored.result.current.draft.idempotencyKey).toBe(original.idempotencyKey)
  const family = renderHook(() => useOrganizerDraft(`${name}:family:a-2`, 'new'))
  await waitFor(() => expect(family.result.current.ready).toBe(true))
  expect(family.result.current.draft.text).toBe('')
  await act(() => restored.result.current.clear())
  expect(restored.result.current.draft.photos).toHaveLength(0)
  restored.unmount()
  family.unmount()
})
