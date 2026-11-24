import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { renderWithI18n as render } from '@vmsh/test-utils/i18n'
import fixture from '@vmsh/contracts/fixtures/review/contribution.v1.json'
import { reviewContributionSchema } from '@vmsh/contracts'

const mocks = vi.hoisted(() => ({
  load: vi.fn(),
  toast: vi.fn(),
  auth: { client: { runtime: { audience: 'staff', instance: 'agent' } }, refresh: vi.fn() },
}))
vi.mock('@vmsh/app-shell', async (original) => ({
  ...(await original<object>()),
  useAuthentication: () => mocks.auth,
  useAuthenticatedPrincipal: () => ({ accountId: 'a-1', audience: 'staff' }),
  createReviewContributionClient: () => mocks.load,
}))
vi.mock('@vmsh/ui', async (original) => ({
  ...(await original<object>()),
  toast: { info: mocks.toast },
}))
import { ReviewContribution } from './review-contribution'

afterEach(() => {
  cleanup()
  vi.resetAllMocks()
})

it('keeps the disclosure mounted when selecting another lesson', async () => {
  const data = reviewContributionSchema.parse(fixture)
  mocks.load
    .mockResolvedValueOnce(data)
    .mockResolvedValue({ ...data, lesson: { ...data.lesson!, number: 10 } })
  mount()
  const summary = (await screen.findByText('Ваш вклад')).closest('summary')!
  act(() => {
    summary.click()
  })
  const selector = screen.getByLabelText('Занятие статистики')
  act(() => {
    selector.focus()
    fireEvent.change(selector, { target: { value: '10' } })
  })
  await screen.findByRole('heading', { name: /^Занятие 10 ·/ })
  expect(summary.parentElement?.hasAttribute('open')).toBe(true)
  expect(screen.getByLabelText('Занятие статистики')).toBe(selector)
  expect(document.activeElement).toBe(selector)
})
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <ReviewContribution />
    </QueryClientProvider>,
  )
  return client
}
it('shows a first confirmed review without celebrating historical data on load', async () => {
  const data = reviewContributionSchema.parse(fixture)
  const zero = {
    ...data,
    allTime: { ...data.allTime, total: 0, plus: 0 },
    lesson: { ...data.lesson!, counts: { ...data.lesson!.counts, total: 0, plus: 0 } },
  }
  const one = {
    ...data,
    allTime: { ...data.allTime, total: 1, plus: 1 },
    milestone: { value: 1, reached: [1], next: 10 },
    lesson: {
      ...data.lesson!,
      counts: { ...data.lesson!.counts, total: 1, plus: 1 },
      milestone: { value: 1, reached: [1], next: 10 },
    },
  }
  mocks.load.mockResolvedValueOnce(zero).mockResolvedValue(one)
  const client = mount()
  await waitFor(() => expect(client.isFetching()).toBe(0))
  expect(screen.queryByText('Ваш вклад')).toBeNull()
  expect(mocks.toast).not.toHaveBeenCalled()
  act(() => {
    window.dispatchEvent(new Event('review-completed'))
  })
  await screen.findByText('Ваш вклад')
  await waitFor(() => expect(mocks.toast).toHaveBeenCalledTimes(1))
  act(() => {
    window.dispatchEvent(new Event('review-completed'))
  })
  await waitFor(() => expect(mocks.load).toHaveBeenCalledTimes(3))
  expect(mocks.toast).toHaveBeenCalledTimes(1)
})

it('preserves a disclosure and focus during refresh, and retains totals on errors', async () => {
  mocks.load.mockResolvedValue(reviewContributionSchema.parse(fixture))
  const client = mount()
  const title = await screen.findByText('Ваш вклад')
  const summary = title.closest('summary')!
  act(() => {
    summary.click()
    summary.focus()
  })
  expect(summary.parentElement?.hasAttribute('open')).toBe(true)
  expect(mocks.toast).not.toHaveBeenCalled()
  mocks.load.mockRejectedValue(new Error('offline'))
  await act(async () => {
    await client.invalidateQueries()
  })
  await screen.findByText('Не удалось обновить показатели')
  expect(document.activeElement).toBe(summary)
  expect(summary.parentElement?.hasAttribute('open')).toBe(true)
  expect(screen.getByText('Не удалось обновить показатели').textContent).toContain(
    'Не удалось обновить показатели',
  )
  expect(
    screen.getByRole('progressbar', { name: 'Ваш общий вклад' }).getAttribute('aria-valuenow'),
  ).toBe('1240')
})

it('acknowledges a new weekly milestone only after an own confirmed save', async () => {
  const data = reviewContributionSchema.parse(fixture)
  const before = {
    ...data,
    weekly: { ...data.weekly, current: 1, best: 1, milestone: { value: 1, reached: [], next: 2 } },
  }
  const after = {
    ...data,
    weekly: { ...data.weekly, current: 2, best: 2, milestone: { value: 2, reached: [2], next: 4 } },
  }
  mocks.load.mockResolvedValueOnce(before).mockResolvedValue(after)
  mount()
  await screen.findByText('Ваш вклад')
  expect(mocks.toast).not.toHaveBeenCalled()
  act(() => {
    window.dispatchEvent(new Event('review-contribution-saved'))
  })
  await waitFor(() => expect(mocks.toast).toHaveBeenCalledWith('2 недели подряд с проверками'))
})
