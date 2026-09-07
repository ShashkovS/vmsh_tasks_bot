import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import type { ReviewLease } from '@vmsh/contracts'
import type * as AppShell from '@vmsh/app-shell'

const mocks = vi.hoisted(() => {
  const client = { list: vi.fn(), claim: vi.fn(), release: vi.fn(), correct: vi.fn() }
  const principal = { accountId: 'u-1', audience: 'staff' as const }
  const authentication = { client: { runtime: {} }, refresh: vi.fn(), handleApiError: vi.fn() }
  return { client, principal, authentication, mounts: new Map<string, number>() }
})
vi.mock('@vmsh/app-shell', async (original) => ({
  ...(await original<typeof AppShell>()),
  useAuthentication: () => mocks.authentication,
  useAuthenticatedPrincipal: () => mocks.principal,
  createReviewQueueClient: () => mocks.client,
  createWrittenMaterialReassignmentClient: () => ({}),
}))
vi.mock('@tanstack/react-router', () => ({
  Link: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}))
vi.mock('./review-workspace-page', async () => {
  const { useEffect } = await import('react')
  return {
    ReviewReadOnlyEvidence: () => null,
    LoadedReviewWorkspace: ({
      queueId,
      inactive,
      onCompleted,
    }: {
      queueId: string
      inactive: boolean
      onCompleted: (response: unknown, draft: unknown) => void
    }) => {
      useEffect(() => {
        mocks.mounts.set(queueId, (mocks.mounts.get(queueId) ?? 0) + 1)
      }, [queueId])
      return (
        <button
          disabled={inactive}
          onClick={() =>
            onCompleted(
              { review: { reviewId: 'r-1' } },
              { verdictValue: 'plus', comment: '', reactionId: null, annotations: [] },
            )
          }
        >
          {queueId}
        </button>
      )
    },
  }
})
import { StaffReviewSeriesPage } from './review-series-page'

function work(id: string) {
  return { queueId: id, logicalCaseId: id, branches: [{ problemId: 'p-1' }], lock: null }
}
function lease(id: string): ReviewLease {
  return {
    claimToken: id,
    logicalCaseId: id,
    branches: [],
    evidenceBranches: [],
    student: { studentId: 'u-2', displayName: 'Ученик' },
    claimedAt: '',
    expiresAt: '',
  }
}
afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  mocks.mounts.clear()
})

it('prepares only one next work, promotes its existing render and releases remaining leases on exit', async () => {
  mocks.client.list.mockResolvedValue({ items: [work('q-1'), work('q-2')], nextCursor: null })
  mocks.client.claim.mockImplementation((id: string) => Promise.resolve({ lease: lease(id) }))
  mocks.client.release.mockResolvedValue({})
  vi.spyOn(window, 'scrollTo').mockImplementation(() => undefined)
  const view = render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <StaffReviewSeriesPage problemId="p-1" />
    </QueryClientProvider>,
  )
  await waitFor(() => expect(mocks.client.claim).toHaveBeenCalledTimes(2))
  await waitFor(() => expect(screen.getAllByRole('button', { name: /^q-/ })).toHaveLength(1))
  const current = screen.getByRole('button', { name: /^q-/ })
  const currentId = current.textContent
  const nextId = currentId === 'q-1' ? 'q-2' : 'q-1'
  expect(mocks.mounts.get(nextId)).toBe(1)
  fireEvent.click(current)
  await waitFor(() => expect(screen.getByRole('button', { name: nextId })).toBeTruthy())
  expect(mocks.mounts.get(nextId)).toBe(1)
  expect(mocks.client.claim).toHaveBeenCalledTimes(2)
  mocks.client.correct.mockResolvedValue({ correction: { reviewId: 'r-2' } })
  fireEvent.click(screen.getByRole('button', { name: /^Исправить предыдущую/ }))
  fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Исправленный комментарий' } })
  fireEvent.keyDown(window, { key: 'Enter', ctrlKey: true })
  await waitFor(() =>
    expect(mocks.client.correct).toHaveBeenCalledWith(
      'r-1',
      expect.objectContaining({ verdict: 17, comment: 'Исправленный комментарий' }),
    ),
  )
  await waitFor(() => expect(screen.getByRole('button', { name: nextId })).toBeTruthy())
  expect(mocks.mounts.get(nextId)).toBe(1)
  view.unmount()
  expect(mocks.client.release).toHaveBeenCalledWith(nextId, nextId)
  expect(mocks.client.release).not.toHaveBeenCalledWith(currentId, currentId)
})

it('releases an in-flight claim that arrives after leaving the series', async () => {
  mocks.client.list.mockResolvedValue({ items: [work('q-1')], nextCursor: null })
  let resolveClaim!: (value: { lease: ReviewLease }) => void
  mocks.client.claim.mockImplementation(
    () =>
      new Promise((resolve) => {
        resolveClaim = resolve
      }),
  )
  mocks.client.release.mockResolvedValue({})
  const view = render(
    <QueryClientProvider client={new QueryClient()}>
      <StaffReviewSeriesPage problemId="p-1" />
    </QueryClientProvider>,
  )
  await waitFor(() => expect(mocks.client.claim).toHaveBeenCalledTimes(1))
  view.unmount()
  resolveClaim({ lease: lease('q-1') })
  await waitFor(() => expect(mocks.client.release).toHaveBeenCalledWith('q-1', 'q-1'))
})
