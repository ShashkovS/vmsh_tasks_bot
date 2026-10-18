import type * as AppShell from '@vmsh/app-shell'
import type * as Offline from '@vmsh/offline'
import type * as Product from '@vmsh/product'
import type { ReactNode } from 'react'
import { act, cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { renderWithI18n as render } from '@vmsh/test-utils/i18n'

const mocks = vi.hoisted(() => {
  const photos: Array<Record<string, unknown>> = []
  let text = ''
  return {
    photos,
    reset: () => {
      text = ''
      photos.length = 0
    },
    store: {
      load: vi.fn(() => Promise.resolve({ compatible: { text, photos: [...photos] } })),
      saveText: vi.fn((_descriptor: unknown, value: string) => {
        text = value
      }),
      addPhoto: vi.fn((_descriptor: unknown, photo: Record<string, unknown>) => {
        photos.push({ ...photo, byteSize: 10 })
        return Promise.resolve()
      }),
    },
    outbox: { list: vi.fn(() => Promise.resolve([])), enqueue: vi.fn(() => new Promise(() => {})) },
    compress: vi.fn(),
    refetch: vi.fn(() => Promise.resolve()),
    database: {},
    authentication: {
      state: {
        status: 'offline-unverified',
        principal: { audience: 'student', accountId: 'u-test' },
      },
      client: { runtime: { instance: 'composer-test' } },
    },
  }
})
vi.mock('@vmsh/app-shell', async (original) => ({
  ...(await original<typeof AppShell>()),
  useAuthentication: () => mocks.authentication,
  useServiceAvailability: () => ({ state: 'available' }),
  useWrittenThreadQuery: () => ({ data: null, refetch: mocks.refetch }),
  useWrittenStudentReactionMutation: () => ({ isPending: false }),
  createWrittenSubmissionClient: () => ({}),
  initializeImageCompression: () => Promise.resolve(),
  reportHandledError: vi.fn(),
}))
vi.mock('@vmsh/offline', async (original) => ({
  ...(await original<typeof Offline>()),
  useOfflineDatabase: () => mocks.database,
  createWrittenSubmissionDraftStore: () => mocks.store,
  createWrittenSubmissionOutbox: () => mocks.outbox,
}))
vi.mock('@vmsh/product', async (original) => ({
  ...(await original<typeof Product>()),
  ChatComposer: ({
    children,
    onSend,
    sendDisabled,
    attachments,
    onRemoveAttachment,
  }: {
    children: ReactNode
    onSend: () => void
    sendDisabled: boolean
    attachments: Array<{ id: string }>
    onRemoveAttachment: (id: string) => void
  }) => (
    <div>
      {children}
      <button disabled={sendDisabled} onClick={onSend}>
        send
      </button>
      {attachments.map(({ id }) => (
        <button key={id} onClick={() => onRemoveAttachment(id)}>
          remove
        </button>
      ))}
    </div>
  ),
}))
vi.mock('./image-compression', () => ({ compressWrittenSubmissionImage: mocks.compress }))
import { StudentWrittenSubmission } from './student-written-submission'

beforeEach(() => {
  mocks.reset()
  vi.clearAllMocks()
  vi.stubGlobal(
    'URL',
    class extends URL {
      static override createObjectURL() {
        return 'blob:synthetic'
      }
      static override revokeObjectURL() {}
    },
  )
  vi.spyOn(window, 'confirm').mockReturnValue(true)
})
afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})
const props = {
  problemId: 'p-1',
  problemType: 'written' as const,
  conditionRevisionId: 'r-1',
  configVersion: 1,
}

it.each([false, true])(
  'waits for every selected photo before click/keyboard Send (text=%s)',
  async (withText) => {
    const finish: Array<() => void> = []
    mocks.compress.mockImplementation(
      (file: File) =>
        new Promise((resolve) => {
          finish.push(() => resolve({ status: 'fallback', source: file }))
        }),
    )
    const { container } = render(<StudentWrittenSubmission {...props} />)
    const field = await screen.findByRole('textbox')
    if (withText) fireEvent.input(field, { target: { value: 'Saved explanation' } })
    fireEvent.change(container.querySelector('input[multiple]')!, {
      target: { files: [new File(['1'], 'one.jpg'), new File(['2'], 'two.jpg')] },
    })
    const send = screen.getByRole('button', { name: 'send' })
    expect(send.hasAttribute('disabled')).toBe(true)
    fireEvent.click(send)
    fireEvent.keyDown(field, { key: 'Enter', ctrlKey: true })
    expect(mocks.outbox.enqueue).not.toHaveBeenCalled()
    await act(async () => {
      finish[0]!()
      await Promise.resolve()
    })
    await waitFor(() => expect(mocks.store.addPhoto).toHaveBeenCalledTimes(1))
    expect(send.hasAttribute('disabled')).toBe(true)
    fireEvent.keyDown(field, { key: 'Enter', metaKey: true })
    expect(mocks.outbox.enqueue).not.toHaveBeenCalled()
    await act(async () => {
      finish[1]!()
      await Promise.resolve()
    })
    await waitFor(() => expect(send.hasAttribute('disabled')).toBe(false))
    expect(mocks.photos).toHaveLength(2)
    fireEvent.keyDown(field, { key: 'Enter', ctrlKey: true })
    expect(mocks.outbox.enqueue).toHaveBeenCalledWith(
      expect.objectContaining({ problemId: 'p-1', ownerId: 'u-test' }),
    )
  },
)
it('keeps a failed page blocking Send until explicitly removed', async () => {
  mocks.compress.mockRejectedValue(new Error('synthetic preparation failure'))
  const { container } = render(<StudentWrittenSubmission {...props} />)
  const field = await screen.findByRole('textbox')
  fireEvent.input(field, { target: { value: 'Saved text' } })
  fireEvent.change(container.querySelector('input[multiple]')!, {
    target: { files: [new File(['1'], 'one.jpg')] },
  })
  await waitFor(() => expect(mocks.compress).toHaveBeenCalled())
  expect(screen.getByRole('button', { name: 'send' }).hasAttribute('disabled')).toBe(true)
  fireEvent.click(screen.getByRole('button', { name: 'remove' }))
  await waitFor(() =>
    expect(screen.getByRole('button', { name: 'send' }).hasAttribute('disabled')).toBe(false),
  )
})
it('aborts old preparation when the published condition changes', async () => {
  let finish!: () => void
  let signal!: AbortSignal
  mocks.compress.mockImplementation((file: File, options: { signal: AbortSignal }) => {
    signal = options.signal
    return new Promise((resolve) => {
      finish = () => resolve({ status: 'fallback', source: file })
    })
  })
  const { container, rerender } = render(<StudentWrittenSubmission {...props} />)
  await screen.findByRole('textbox')
  fireEvent.change(container.querySelector('input[multiple]')!, {
    target: { files: [new File(['1'], 'one.jpg')] },
  })
  rerender(<StudentWrittenSubmission {...props} conditionRevisionId="r-2" />)
  await screen.findByRole('textbox')
  expect(signal.aborted).toBe(true)
  await act(async () => {
    finish()
    await Promise.resolve()
  })
  expect(mocks.store.addPhoto).not.toHaveBeenCalled()
})
