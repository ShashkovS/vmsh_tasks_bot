import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { OralWeeklyDraft } from './oral-weekly-draft'
import type { createStaffOralWindowClient } from '@vmsh/app-shell'

const window = {
  windowId: 'ow-1',
  sequenceNumber: 1,
  opensAt: '2026-10-05T15:00:00Z',
  closesAt: '2026-10-05T17:00:00Z',
  joinLabel: 'Наш Zoom',
  joinUrl: 'https://zoom.example.test/1',
  joinCode: '179',
  state: 'closed' as const,
  joinAvailable: false,
  version: 1,
  status: 'active' as const,
}
beforeEach(() => {
  const values = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
    clear: () => values.clear(),
  })
})
function setup() {
  const client = {
    planning: vi.fn().mockResolvedValue({
      groups: [
        { groupLessonId: 'gl-1', groupName: 'Начинающие' },
        { groupLessonId: 'gl-2', groupName: 'Продолжающие' },
      ],
      courseName: 'ВМШ',
      lessonNumber: 2,
      previous: [{ window, groupLessonIds: ['gl-1', 'gl-2'] }],
    }),
    saveBatch: vi
      .fn<ReturnType<typeof createStaffOralWindowClient>['saveBatch']>()
      .mockResolvedValue({ schemaVersion: 1, requestId: 'test', items: [] }),
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
  }
  const query = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={query}>
      <OralWeeklyDraft client={client} accountId="a-1" groupLessonId="gl-1" onSaved={vi.fn()} />
    </QueryClientProvider>,
  )
  return client
}
afterEach(() => {
  cleanup()
  localStorage.clear()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})
it('copies the previous week into an editable three-day draft and excludes Tuesday', async () => {
  vi.spyOn(globalThis, 'confirm').mockReturnValue(true)
  const user = userEvent.setup(),
    client = setup()
  await user.click(await screen.findByRole('button', { name: 'С прошлого занятия (+7 дней)' }))
  await waitFor(() =>
    expect(screen.getByLabelText<HTMLInputElement>('HTTPS-ссылка').value).toBe(window.joinUrl),
  )
  expect(screen.getByLabelText<HTMLInputElement>('Открывается').value).toContain('2026-10-12')
  expect(client.saveBatch).not.toHaveBeenCalled()
  await user.click(screen.getByRole('button', { name: 'Пн / вт / ср' }))
  await user.click(screen.getByRole('checkbox', { name: 'Окно 2' }))
  await user.click(screen.getByRole('button', { name: 'Создать выбранные окна' }))
  await waitFor(() => expect(client.saveBatch).toHaveBeenCalledTimes(1))
  const batch = client.saveBatch.mock.calls[0]![1]
  expect(batch.entries).toHaveLength(2)
  expect(
    batch.entries.map((e: { window: { opensAt: string } }) => e.window.opensAt.slice(0, 10)),
  ).toEqual(['2026-10-12', '2026-10-14'])
  expect(batch.entries[0]?.groupLessonIds).toEqual(['gl-1', 'gl-2'])
})
it('locks an uncertain draft and retries using the same idempotency key', async () => {
  vi.spyOn(globalThis, 'confirm').mockReturnValue(true)
  const user = userEvent.setup(),
    client = setup()
  client.saveBatch.mockRejectedValueOnce(new TypeError('network'))
  await user.click(await screen.findByRole('button', { name: 'С прошлого занятия (+7 дней)' }))
  await waitFor(() =>
    expect(screen.getByLabelText<HTMLInputElement>('HTTPS-ссылка').value).toBe(window.joinUrl),
  )
  await user.click(screen.getByRole('button', { name: 'Создать выбранные окна' }))
  await user.click(await screen.findByRole('button', { name: 'Повторить сохранение' }))
  await waitFor(() => expect(client.saveBatch).toHaveBeenCalledTimes(2))
  expect(client.saveBatch.mock.calls[0]![1]).toEqual(client.saveBatch.mock.calls[1]![1])
})
