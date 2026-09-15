import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import type { ReviewQueueClient } from '@vmsh/app-shell'
import { ReviewTransfer } from './review-transfer'

afterEach(cleanup)
it('confirms one complete entry and retries the exact same idempotency request after network failure', async () => {
  const preview = vi.fn().mockResolvedValue({
    schemaVersion: 1,
    entryId: 'se-1',
    sourceVersion: 2,
    entryVersion: 3,
    studentName: 'Анна Белова',
    sourceLabel: '1н.1 · Исходная',
    photoCount: 2,
    targets: [{ problemId: 'p-2', label: '1н.2 · Целевая', threadVersion: 4, threadId: 'st-2' }],
  })
  const transfer = vi.fn().mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce({
    schemaVersion: 1,
    mode: 'clone',
    sourceEntryId: 'se-1',
    targetEntryId: 'se-2',
    targetProblemId: 'p-2',
    targetLabel: '1н.2 · Целевая',
  })
  const onDone = vi.fn().mockResolvedValue(undefined)
  render(
    <ReviewTransfer
      client={{ transferPreview: preview, transfer } as unknown as ReviewQueueClient}
      queueId="wq-1"
      entryId="se-1"
      claimToken="claim-1"
      disabled={false}
      onBusy={() => undefined}
      onDone={onDone}
    />,
  )
  fireEvent.click(screen.getByRole('button', { name: 'Клонировать в другую задачу' }))
  await screen.findByText(/Анна Белова/)
  expect(preview).toHaveBeenCalledWith('wq-1', 'se-1', 'claim-1')
  fireEvent.change(screen.getByLabelText('Целевая задача'), { target: { value: 'p-2' } })
  fireEvent.click(screen.getByRole('button', { name: 'Клонировать посылку' }))
  await screen.findByRole('alert')
  expect(onDone).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Повторить запрос' }))
  await waitFor(() => expect(onDone).toHaveBeenCalledTimes(1))
  expect(transfer.mock.calls[1]).toEqual(transfer.mock.calls[0])
  expect(transfer.mock.calls[0]?.[1]).toEqual(
    expect.objectContaining({
      entryId: 'se-1',
      mode: 'clone',
      sourceVersion: 2,
      entryVersion: 3,
      targetVersion: 4,
    }),
  )
})
