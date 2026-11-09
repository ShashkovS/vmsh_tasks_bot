import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, screen, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import type { ReactNode } from 'react'
import { reviewQueueListResponseSchema, type ReviewQueueItem } from '@vmsh/contracts'
import { renderWithI18n as render } from '@vmsh/test-utils/i18n'

const mocks = vi.hoisted(() => {
  const search: { queueGroup?: string; queueView?: 'works' } = {}
  return {
    search,
    client: { list: vi.fn(), claim: vi.fn() },
    principal: { accountId: 'staff-one', audience: 'staff' as const },
    authentication: {
      client: { runtime: { audience: 'staff', instance: 'agent' } },
      refresh: vi.fn(),
      handleApiError: vi.fn(),
    },
  }
})
vi.mock('@vmsh/app-shell', async (original) => ({
  ...(await original<object>()),
  useAuthentication: () => mocks.authentication,
  useAuthenticatedPrincipal: () => mocks.principal,
  createReviewQueueClient: () => mocks.client,
}))
vi.mock('@tanstack/react-router', () => ({
  Link: ({ children }: { children: ReactNode }) => <a href="/staff/review">{children}</a>,
  useNavigate: () => vi.fn(),
}))
vi.mock('./routes/review', () => ({ Route: { useSearch: () => mocks.search } }))

import { StaffReviewQueuePage } from './review-queue-page'

afterEach(() => {
  cleanup()
  mocks.search = {}
  vi.resetAllMocks()
})

// Wire identities and visible counters: docs/serial-review.md and review-queue-report.md.
it('shows all students across queue pages in summary, task cards, filters and the works table', async () => {
  const items: ReviewQueueItem[] = Array.from({ length: 52 }, (_, index) => ({
    queueId: `q-${index}`,
    logicalCaseId: 'synonym-shared',
    student: { studentId: null, displayName: `Ученик ${index}` },
    submittedAt: '2026-09-01T12:00:00Z',
    lock:
      index < 2
        ? {
            kind: 'pwa',
            teacher: { teacherId: 'staff-two', displayName: 'Коллега' },
            expiresAt: '2026-10-04T12:00:00Z',
            isOwnedByCurrentStaff: index === 0,
          }
        : null,
    branches: [
      {
        queueId: `q-${index}`,
        problemId: 'problem-one',
        problemNumber: '1н.1',
        problemTitle: 'Квадрат',
        courseId: 'course-one',
        courseName: 'Математика',
        groupId: 'group-one',
        groupName: 'Начинающие',
        groupShortCode: 'н',
        groupColorKey: null,
        submittedAt: '2026-09-01T12:00:00Z',
        leaseVersion: 0,
      },
    ],
  }))
  items[0]!.branches.push({
    ...items[0]!.branches[0]!,
    queueId: 'q-peer',
    problemId: 'problem-two',
    problemNumber: '1п.1',
    groupId: 'group-two',
    groupName: 'Продолжающие',
    groupShortCode: 'п',
  })
  mocks.client.list.mockImplementation(({ cursor }: { cursor?: string }) =>
    Promise.resolve(
      reviewQueueListResponseSchema.parse({
        schemaVersion: 1,
        items: cursor ? items.slice(50) : items.slice(0, 50),
        nextCursor: cursor ? null : 'q-49',
        requestId: 'request-one',
      }),
    ),
  )
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const page = () => (
    <QueryClientProvider client={client}>
      <StaffReviewQueuePage />
    </QueryClientProvider>
  )
  const view = render(page())
  const card = await screen.findByRole('article', { name: '1н.1 · Квадрат' })
  expect(screen.getAllByRole('definition').map((value) => value.textContent)).toEqual([
    '52 работы',
    '51 работа',
    '1 работа',
  ])
  expect(card.textContent).toContain('Ждут проверки: 52 работы')
  expect(card.textContent).toContain('Можно проверить: 51 · У других преподавателей: 1')
  expect(screen.getByRole('article', { name: '1п.1 · Квадрат' }).textContent).toContain(
    'Ждут проверки: 1 работа',
  )
  expect(mocks.client.list).toHaveBeenCalledTimes(2)

  mocks.search = { queueView: 'works' }
  view.rerender(page())
  expect(within(screen.getByRole('table')).getAllByRole('row')).toHaveLength(53)
  expect(screen.getAllByRole('definition')[0]!.textContent).toBe('52 работы')

  mocks.search = { queueGroup: 'group-two' }
  view.rerender(page())
  expect(screen.getAllByRole('definition').map((value) => value.textContent)).toEqual([
    '1 работа',
    '1 работа',
    '0 работ',
  ])
  expect(screen.queryByRole('article', { name: '1н.1 · Квадрат' })).toBeNull()
  expect(screen.getByRole('article', { name: '1п.1 · Квадрат' }).textContent).toContain(
    'Ждут проверки: 1 работа',
  )
  expect(mocks.client.claim).not.toHaveBeenCalled()
})
