import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { reviewConversationEventSchema } from '@vmsh/contracts'
import type { ReviewQueueClient } from '@vmsh/app-shell'
import { renderWithI18n as render } from '@vmsh/test-utils/i18n'
import { ReviewConversation } from './review-conversation'

afterEach(cleanup)

function event(id: string, text: string, teacher = false) {
  return reviewConversationEventSchema.parse({
    id,
    kind: teacher ? 'review' : 'discussion',
    problemNumber: '2п.11а',
    at: '2026-09-20T12:00:00Z',
    author: teacher ? 'Учитель' : 'Школьник',
    authorKind: teacher ? 'teacher' : 'student',
    source: teacher ? 'staff' : 'telegram',
    text,
    verdict: teacher ? 14 : null,
    symbol: '',
    revisionId: null,
    attachments: [],
    reviewId: teacher ? 'r-2' : null,
    internal: false,
    action: null,
    transfer: null,
    checkStatus: null,
  })
}
function page(events: ReturnType<typeof event>[], nextCursor: string | null = null) {
  return { schemaVersion: 1 as const, requestId: 'test', events, nextCursor, total: 51 }
}
function mount(client: Pick<ReviewQueueClient, 'conversation'>) {
  const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queries}>
      <ReviewConversation
        client={client}
        reviewId="r-1"
        accountId="a-1"
        namespace="agent"
        threadVersion={1}
      />
    </QueryClientProvider>,
  )
}

// docs/review-history.md: a selected old verdict must show both sides and later replies.
it('renders pupil replies and verdicts chronologically without links to other reviews', async () => {
  const client = {
    conversation: vi
      .fn<ReviewQueueClient['conversation']>()
      .mockResolvedValue(
        page([
          event('discussion:1', 'Первый ответ школьника'),
          event('review:2', 'Уточните обоснование', true),
          event('discussion:3', 'Поздний исправленный ответ'),
        ]),
      ),
  }
  mount(client)
  await screen.findByText('Поздний исправленный ответ')
  const messages = screen.getAllByRole('listitem')
  expect(messages[0]?.textContent).toContain('Первый ответ школьника')
  expect(messages[1]?.textContent).toContain('Уточните обоснование')
  expect(messages[2]?.textContent).toContain('Поздний исправленный ответ')
  expect(screen.getByRole('region', { name: 'История переписки и проверок' })).toBeTruthy()
  expect(screen.queryByRole('link', { name: 'Открыть проверку' })).toBeNull()
  expect(client.conversation).toHaveBeenCalledWith('r-1', undefined, {
    signal: expect.any(AbortSignal),
  })
})

it('keeps loaded replies after a failed next page and retries the same cursor', async () => {
  const client = {
    conversation: vi
      .fn<ReviewQueueClient['conversation']>()
      .mockResolvedValueOnce(page([event('discussion:1', 'Сохранённый ответ')], 'discussion:50'))
      .mockRejectedValueOnce(new Error('unavailable'))
      .mockResolvedValueOnce(page([event('discussion:51', 'Последний ответ')])),
  }
  mount(client)
  await screen.findByText('Сохранённый ответ')
  fireEvent.click(screen.getByRole('button', { name: /Ещё 50 событий/ }))
  await screen.findByRole('alert')
  expect(screen.getByText('Сохранённый ответ')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'Повторить' }))
  await screen.findByText('Последний ответ')
  expect(client.conversation.mock.calls.slice(1).map((args) => args[1])).toEqual([
    'discussion:50',
    'discussion:50',
  ])
  expect(screen.queryByRole('button', { name: /Ещё 50 событий/ })).toBeNull()
})

it('shows a retryable initial error and the explicit empty state', async () => {
  const client = {
    conversation: vi
      .fn<ReviewQueueClient['conversation']>()
      .mockRejectedValueOnce(new Error('unavailable'))
      .mockResolvedValueOnce({ ...page([]), total: 0 }),
  }
  mount(client)
  await screen.findByRole('alert')
  fireEvent.click(screen.getByRole('button', { name: 'Повторить' }))
  await waitFor(() => expect(screen.getByText('Сохранённых событий нет.')).toBeTruthy())
})
