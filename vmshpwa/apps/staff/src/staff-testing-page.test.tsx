import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { StaffTestingPage } from './staff-testing-page'

vi.mock('@vmsh/app-shell', async (original) => ({
  ...(await original<object>()),
  useAuthentication: () => ({
    client: { runtime: { apiBase: '/staff/api/v1' } },
    refresh: vi.fn(),
  }),
  useAuthenticatedPrincipal: () => ({ accountId: 'a-1' }),
}))

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function mount(view: 'tasks' | 'news' | 'courses' = 'tasks') {
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <StaffTestingPage view={view} />
    </QueryClientProvider>,
  )
}

it('lists scoped courses, warns about Student session and enters only after a click', async () => {
  const assign = vi.fn()
  vi.stubGlobal('location', { assign })
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          courses: [
            {
              courseId: 'c-1',
              name: 'Математика',
              groups: [{ groupId: 'g-1', name: 'Начинающие' }],
            },
          ],
        }),
      ),
    )
    .mockResolvedValueOnce(new Response(JSON.stringify({ ready: true })))
  vi.stubGlobal('fetch', fetcher)
  mount('courses')
  expect(await screen.findByText('Математика')).toBeTruthy()
  expect(screen.getByText(/Текущий вход в кабинет школьника/)).toBeTruthy()
  expect(fetcher).toHaveBeenCalledTimes(1)
  fireEvent.click(screen.getByRole('button', { name: 'Открыть как школьник' }))
  await waitFor(() => expect(assign).toHaveBeenCalledWith('/student/tasks?course=c-1'))
  expect(fetcher).toHaveBeenLastCalledWith(
    '/staff/api/v1/testing/session',
    expect.objectContaining({ method: 'POST', credentials: 'include' }),
  )
})

it('shows empty scope without an entry action', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ courses: [] }))))
  mount()
  expect(await screen.findByText('Вам пока не назначены активные курсы и группы.')).toBeTruthy()
  expect(screen.queryByRole('button')).toBeNull()
})

it('shows failed entry without navigating and allows retry', async () => {
  const assign = vi.fn()
  vi.stubGlobal('location', { assign })
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            courses: [
              {
                courseId: 'c-1',
                name: 'Математика',
                groups: [{ groupId: 'g-1', name: 'Начинающие' }],
              },
            ],
          }),
        ),
      )
      .mockRejectedValueOnce(new Error('Нет соединения с сервером')),
  )
  mount('news')
  fireEvent.click(await screen.findByRole('button', { name: 'Читать новости как школьник' }))
  expect((await screen.findByRole('alert')).textContent).toContain('Нет соединения с сервером')
  expect(assign).not.toHaveBeenCalled()
  expect(
    screen.getByRole('button', { name: 'Читать новости как школьник' }).hasAttribute('disabled'),
  ).toBe(false)
})
