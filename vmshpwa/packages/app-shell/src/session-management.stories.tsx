import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, screen, userEvent, waitFor, within } from 'storybook/test'

import studentAuthFixture from '@vmsh/contracts/fixtures/auth/student.v1.json'
import {
  authSessionsResponseSchema,
  type AuthSessionSummary,
  type SessionPublicId,
} from '@vmsh/contracts'

import { SessionManagementView, type SessionManagementLoadState } from './session-management'

const fixtureSessions = authSessionsResponseSchema.parse(
  studentAuthFixture.sessionsResponse,
).sessions

const multipleSessions = authSessionsResponseSchema.parse({
  audience: 'student',
  sessions: [
    ...fixtureSessions,
    {
      sessionId: '00000000000000000000000000000003',
      audience: 'student',
      isCurrent: false,
      deviceLabel: 'Планшет для занятий',
      userAgentFamily: 'Safari на iPadOS',
      createdAt: '2026-07-22T12:00:00Z',
      lastSeenAt: '2026-07-26T17:20:00Z',
      expiresAt: '2026-08-09T21:00:00Z',
    },
  ],
}).sessions

function stateWithSessions(sessions: readonly AuthSessionSummary[]): SessionManagementLoadState {
  return { status: 'ready', sessions }
}

function noopEndSession(): Promise<void> {
  return Promise.resolve()
}

function MutableSessionList() {
  const [sessions, setSessions] = useState(multipleSessions)
  return (
    <SessionManagementView
      onEndSession={(intent) => {
        if (intent.kind === 'other') {
          setSessions((current) =>
            current.filter((session) => session.sessionId !== intent.sessionId),
          )
        }
        return Promise.resolve()
      }}
      state={stateWithSessions(sessions)}
    />
  )
}

const meta = {
  title: 'Product/Account sessions',
  component: SessionManagementView,
} satisfies Meta<typeof SessionManagementView>
export default meta
type Story = StoryObj<typeof meta>

export const Loading: Story = {
  args: { state: { status: 'loading' }, onEndSession: noopEndSession },
}

export const CurrentDevice: Story = {
  args: {
    state: stateWithSessions([fixtureSessions[0]!]),
    onEndSession: noopEndSession,
  },
}

export const MultipleDevices: Story = {
  args: { state: { status: 'loading' }, onEndSession: noopEndSession },
  render: () => <MutableSessionList />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.click(
      canvas.getByRole('button', { name: /завершить сессию на устройстве Synthetic Mobile/i }),
    )
    const dialog = await screen.findByRole('dialog')
    await expect(within(dialog).getByText(/Synthetic Mobile/)).toBeInTheDocument()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Подтвердить' }))
    await waitFor(() =>
      expect(
        canvas.queryByRole('button', {
          name: /завершить сессию на устройстве Synthetic Mobile/i,
        }),
      ).not.toBeInTheDocument(),
    )
  },
}

export const RevokePending: Story = {
  args: {
    state: stateWithSessions(multipleSessions),
    onEndSession: () => new Promise<void>(() => undefined),
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.click(
      canvas.getByRole('button', { name: /завершить сессию на устройстве Synthetic Mobile/i }),
    )
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Подтвердить' }))
    await expect(within(dialog).getByRole('button', { name: 'Завершаем…' })).toBeDisabled()
  },
}

export const RevokeError: Story = {
  args: {
    state: stateWithSessions(multipleSessions),
    onEndSession: () => Promise.reject(new Error('Synthetic transport error')),
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.click(
      canvas.getByRole('button', { name: /завершить сессию на устройстве Synthetic Mobile/i }),
    )
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Подтвердить' }))
    await expect(await canvas.findByRole('alert')).toHaveTextContent('Сессия не изменена')
  },
}

export const EmptyFailsClosed: Story = {
  args: {
    state: stateWithSessions([]),
    onEndSession: noopEndSession,
    onRetry: () => undefined,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByRole('alert')).toHaveTextContent('Список сессий не подтверждён')
    await expect(canvas.queryByRole('button', { name: /выйти на всех/i })).not.toBeInTheDocument()
  },
}

export const CorruptFailsClosed: Story = {
  args: {
    state: stateWithSessions([
      fixtureSessions[0]!,
      {
        ...fixtureSessions[1]!,
        isCurrent: true,
      },
    ]),
    onEndSession: noopEndSession,
    onRetry: () => undefined,
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByRole('alert')).toHaveTextContent('противоречивый список')
    await expect(canvas.queryByRole('list', { name: 'Активные сессии' })).not.toBeInTheDocument()
  },
}

export const LogoutWithOfflineQueueWarning: Story = {
  args: {
    state: stateWithSessions(multipleSessions),
    onEndSession: noopEndSession,
    offlineWorkGuard: {
      inspect: () => ({ status: 'pending', queuedCount: 2 }),
    },
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.click(canvas.getByRole('button', { name: 'Выйти на всех устройствах' }))
    const dialog = await screen.findByRole('dialog')
    await expect(within(dialog).getByRole('alert')).toHaveTextContent(
      'В локальной очереди 2 неотправленных действия',
    )
    await userEvent.click(within(dialog).getByRole('button', { name: 'Отмена' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  },
}

export const NetworkError: Story = {
  args: {
    state: { status: 'error', kind: 'network' },
    onEndSession: noopEndSession,
    onRetry: () => undefined,
  },
}

// Compile-time proof that opaque identifiers stay internal to actions rather
// than becoming device labels or visible controls.
void (fixtureSessions[0]!.sessionId satisfies SessionPublicId)
