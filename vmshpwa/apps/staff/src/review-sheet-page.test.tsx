import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import type * as AppShell from '@vmsh/app-shell'
import {
  ApiResponseError,
  type ReviewSheetDetail,
  type ReviewSheetCollection,
} from '@vmsh/contracts'
import { renderWithI18n as render } from '@vmsh/test-utils/i18n'

const mocks = vi.hoisted(() => ({
  client: {
    sheetOptions: vi.fn(),
    sheet: vi.fn(),
    sheetDetail: vi.fn(),
    sheetConversation: vi.fn(),
    sheetComplete: vi.fn(),
    sheetTransferPreview: vi.fn(),
    sheetTransfer: vi.fn(),
  },
  auth: {
    client: { runtime: { audience: 'staff', instance: 'agent' } },
    refresh: vi.fn(),
    handleApiError: vi.fn(),
  },
}))
vi.mock('@vmsh/app-shell', async (original) => ({
  ...(await original<typeof AppShell>()),
  useAuthentication: () => mocks.auth,
  useAuthenticatedPrincipal: () => ({ accountId: 'a-1', audience: 'staff' }),
  createReviewQueueClient: () => mocks.client,
  createWrittenMaterialReassignmentClient: () => ({}),
}))
import { StaffReviewSheetPage } from './review-sheet-page'

function detail(id: string, snapshot = 'a'.repeat(64)): ReviewSheetDetail {
  const name = id === 'st-1' ? 'Анна' : 'Борис'
  return {
    schemaVersion: 1,
    requestId: 'detail',
    caseId: id,
    snapshot,
    pending: true,
    canReview: true,
    annotations: [],
    currentReview: null,
    workspace: {
      logicalCaseId: id,
      student: { studentId: `u-${id}`, displayName: name },
      verdictMode: 'verdict_plus_steps',
      branches: [
        {
          queueId: id,
          problemId: 'p-1',
          problemNumber: '1н.1',
          problemTitle: 'Задача',
          courseId: 'c-1',
          courseName: 'Математика',
          groupId: 'g-1',
          groupName: 'Группа',
          groupShortCode: 'н',
          groupColorKey: null,
          submittedAt: '2026-10-11T12:00:00Z',
          leaseVersion: 0,
        },
      ],
      evidenceBranches: [
        {
          queueId: id,
          thread: {
            threadId: id,
            threadVersion: 1,
            entries: [
              {
                entryId: `se-${id}`,
                entryVersion: 1,
                entryKind: 'submission',
                text: `${name}: решение`,
                submittedAt: '2026-10-11T12:00:00Z',
                attachments: [],
              },
            ],
            timelineEntries: [
              {
                entryId: `se-${id}`,
                authorKind: 'student',
                entryKind: 'submission',
                text: `${name}: решение`,
                submittedAt: '2026-10-11T12:00:00Z',
                attachments: [],
              },
            ],
          },
        },
      ],
    },
  }
}
function collection(total = 2): ReviewSheetCollection {
  return {
    schemaVersion: 1,
    requestId: 'sheet',
    lessonId: 'gl-1',
    total,
    limit: 300,
    canOpenLesson: total <= 300,
    tasks: [
      {
        problemId: 'p-1',
        label: '1н.1 · Задача',
        count: total,
        parts:
          total <= 300
            ? [
                {
                  problemId: 'p-1',
                  label: '1н.1',
                  condition: null,
                  statement: 'Условие всей задачи',
                },
              ]
            : [],
        cases:
          total <= 300
            ? ['st-1', 'st-2'].map((caseId) => ({
                caseId,
                problemId: 'p-1',
                studentName: caseId === 'st-1' ? 'Анна' : 'Борис',
                submittedAt: '2026-10-11T12:00:00Z',
                pending: true,
              }))
            : [],
      },
    ],
  }
}
beforeEach(() => {
  vi.clearAllMocks()
  const values = new Map<string, string>()
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    value: {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
      removeItem: (key: string) => values.delete(key),
      clear: () => values.clear(),
    },
  })
  mocks.client.sheetOptions.mockResolvedValue({
    lessons: [{ lessonId: 'gl-1', label: 'Математика · 1н' }],
  })
  mocks.client.sheet.mockResolvedValue(collection())
  mocks.client.sheetDetail.mockImplementation((id: string) => Promise.resolve(detail(id)))
  mocks.client.sheetConversation.mockResolvedValue({ events: [], nextCursor: null, total: 0 })
  mocks.client.sheetComplete.mockResolvedValue({ review: { reviewId: 'r-1' } })
})
afterEach(cleanup)
function mount(queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  const change = vi.fn()
  render(
    <QueryClientProvider client={queryClient}>
      <StaffReviewSheetPage search={{ lesson: 'gl-1', mode: 'pending' }} onSearchChange={change} />
    </QueryClientProvider>,
  )
  return change
}

it('only submits the focused card and leaves other drafts intact', async () => {
  mount()
  const anna = await screen.findByRole('article', { name: 'Проверка работы: Анна' })
  const boris = screen.getByRole('article', { name: 'Проверка работы: Борис' })
  await within(anna).findByRole('textbox', { name: 'Комментарий' })
  const otherComment = await within(boris).findByRole('textbox', { name: 'Комментарий' })
  fireEvent.change(otherComment, { target: { value: 'Черновик Бориса' } })
  fireEvent.click(within(boris).getByRole('button', { name: '1 Зачтено' }))
  fireEvent.click(within(anna).getByRole('button', { name: '1 Зачтено' }))
  const comment = within(anna).getByRole('textbox', { name: 'Комментарий' })
  fireEvent.change(comment, { target: { value: 'Проверка Анны' } })
  act(() => comment.focus())
  fireEvent.keyDown(window, { key: 'Enter', ctrlKey: true })
  await waitFor(() => expect(mocks.client.sheetComplete).toHaveBeenCalledTimes(1))
  expect(mocks.client.sheetComplete.mock.calls[0]?.[0]).toBe('st-1')
  expect((otherComment as HTMLTextAreaElement).value).toBe('Черновик Бориса')
  await within(anna).findByText('Результат отправлен')
})

it('refreshes just the conflicted dialogue and preserves comment/verdict for explicit resend', async () => {
  mocks.client.sheetComplete.mockRejectedValueOnce(
    new ApiResponseError(409, {
      error: {
        code: 'review_sheet_changed',
        message: 'Работа уже проверена',
        requestId: 'conflict',
      },
    }),
  )
  mount()
  const anna = await screen.findByRole('article', { name: 'Проверка работы: Анна' })
  const comment = await within(anna).findByRole('textbox', { name: 'Комментарий' })
  fireEvent.change(comment, { target: { value: 'Мой комментарий' } })
  fireEvent.click(within(anna).getByRole('button', { name: '1 Зачтено' }))
  mocks.client.sheetDetail.mockImplementation((id: string) =>
    Promise.resolve(detail(id, id === 'st-1' ? 'b'.repeat(64) : 'a'.repeat(64))),
  )
  fireEvent.click(within(anna).getByRole('button', { name: 'Отправить вердикт' }))
  await within(anna).findByRole('button', { name: 'Отправить мой результат' })
  await waitFor(() =>
    expect(
      within(anna)
        .getByRole('button', { name: 'Отправить мой результат' })
        .hasAttribute('disabled'),
    ).toBe(false),
  )
  expect((comment as HTMLTextAreaElement).value).toBe('Мой комментарий')
  expect(mocks.client.sheetDetail.mock.calls.filter(([id]) => id === 'st-2')).toHaveLength(1)
  fireEvent.click(within(anna).getByRole('button', { name: 'Отправить мой результат' }))
  await within(anna).findByText('Результат отправлен')
  const first = mocks.client.sheetComplete.mock.calls[0]?.[1]
  const second = mocks.client.sheetComplete.mock.calls[1]?.[1]
  expect(second).toMatchObject({
    snapshot: 'b'.repeat(64),
    comment: 'Мой комментарий',
    verdict: 17,
  })
  expect(second.idempotencyKey).not.toBe(first.idempotencyKey)
})

it('can abandon one review without touching the other form', async () => {
  mount()
  const anna = await screen.findByRole('article', { name: 'Проверка работы: Анна' })
  await within(anna).findByRole('textbox')
  fireEvent.click(within(anna).getByRole('button', { name: 'Отказаться от проверки' }))
  await within(anna).findByText('Вы отказались от этой проверки')
  const boris = screen.getByRole('article', { name: 'Проверка работы: Борис' })
  expect((await within(boris).findByRole('textbox')).hasAttribute('disabled')).toBe(false)
  expect(mocks.client.sheetComplete).not.toHaveBeenCalled()
})

it('keeps opened cards, drafts and CAS snapshots when background resync shrinks the queue', async () => {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  mount(queryClient)
  const anna = await screen.findByRole('article', { name: 'Проверка работы: Анна' })
  const comment = await within(anna).findByRole('textbox', { name: 'Комментарий' })
  fireEvent.change(comment, { target: { value: 'Сохранённый черновик' } })
  fireEvent.click(within(anna).getByRole('button', { name: '1 Зачтено' }))
  const remaining = collection(1)
  remaining.tasks[0]!.cases = remaining.tasks[0]!.cases.filter((item) => item.caseId === 'st-2')
  mocks.client.sheet.mockResolvedValue(remaining)
  mocks.client.sheetDetail.mockImplementation((id: string) =>
    Promise.resolve(detail(id, 'b'.repeat(64))),
  )
  await act(async () => {
    await queryClient.refetchQueries()
  })
  expect(screen.getAllByRole('article')).toHaveLength(2)
  expect((comment as HTMLTextAreaElement).value).toBe('Сохранённый черновик')
  fireEvent.click(within(anna).getByRole('button', { name: 'Отправить вердикт' }))
  await within(anna).findByText('Результат отправлен')
  expect(mocks.client.sheetComplete.mock.calls[0]?.[1].snapshot).toBe('a'.repeat(64))
  expect(screen.getAllByRole('article')).toHaveLength(2)
})

it('blocks a 301-card lesson while offering task selection and the all toggle', async () => {
  mocks.client.sheet.mockResolvedValue(collection(301))
  const change = mount()
  await screen.findByText(/301 работ/)
  expect(
    screen.getByRole('button', { name: 'Показать все решения' }).hasAttribute('disabled'),
  ).toBe(true)
  expect(screen.queryByRole('article')).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: '1н.1 · Задача · 301' }))
  expect(change).toHaveBeenCalledWith({ lesson: 'gl-1', problem: 'p-1', mode: 'pending' })
  fireEvent.click(screen.getByRole('button', { name: 'Все' }))
  expect(change).toHaveBeenCalledWith({ lesson: 'gl-1', mode: 'all' })
})
