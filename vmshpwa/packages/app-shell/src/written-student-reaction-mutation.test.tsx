import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { writtenSubmissionQueryKeys, type WrittenStudentReactionResponse } from '@vmsh/contracts'

import { AppProviders, createAppQueryClient } from './providers'
import { useWrittenStudentReactionMutation } from './written-submission-client'

const principal = { audience: 'student' as const, accountId: 'student-reaction-account' }
const problemId = 'student-reaction-problem'
const reviewId = 'student-reaction-review'

function response(reactionId: 0 | null, version: number): WrittenStudentReactionResponse {
  return {
    schemaVersion: 1,
    reviewId,
    studentReaction: {
      reactionId,
      version,
      editableUntil: '2026-09-21T11:00:00.000000Z',
      updatedAt: '2026-09-21T10:10:00.000000Z',
      deleted: reactionId === null,
    },
    requestId: `student-reaction-request-${version}`,
  }
}

afterEach(cleanup)

describe('Student review reaction mutation', () => {
  it('chooses PUT/DELETE semantics and invalidates the concrete owner thread', async () => {
    const client = {
      setStudentReaction: vi.fn(() => Promise.resolve(response(0, 1))),
      deleteStudentReaction: vi.fn(() => Promise.resolve(response(null, 2))),
    }
    const queryClient = createAppQueryClient()
    const threadKey = writtenSubmissionQueryKeys.thread(principal, problemId)
    queryClient.setQueryData(threadKey, { marker: 'thread-before-reaction' })

    function Harness() {
      const mutation = useWrittenStudentReactionMutation(client, principal, problemId)
      return (
        <>
          <button
            onClick={() => mutation.mutate({ reviewId, reactionId: 0, expectedVersion: 0 })}
            type="button"
          >
            Выбрать
          </button>
          <button
            onClick={() => mutation.mutate({ reviewId, reactionId: null, expectedVersion: 1 })}
            type="button"
          >
            Снять
          </button>
        </>
      )
    }

    render(
      <AppProviders queryClient={queryClient}>
        <Harness />
      </AppProviders>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Выбрать' }))
    await waitFor(() => expect(client.setStudentReaction).toHaveBeenCalledOnce())
    expect(client.setStudentReaction).toHaveBeenCalledWith(reviewId, {
      schemaVersion: 1,
      reactionId: 0,
      expectedVersion: 0,
    })
    expect(queryClient.getQueryState(threadKey)?.isInvalidated).toBe(true)

    queryClient.setQueryData(threadKey, { marker: 'thread-after-selection' })
    fireEvent.click(screen.getByRole('button', { name: 'Снять' }))
    await waitFor(() => expect(client.deleteStudentReaction).toHaveBeenCalledOnce())
    expect(client.deleteStudentReaction).toHaveBeenCalledWith(reviewId, {
      schemaVersion: 1,
      expectedVersion: 1,
    })
    expect(queryClient.getQueryState(threadKey)?.isInvalidated).toBe(true)
  })
})
