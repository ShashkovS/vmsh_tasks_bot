import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import { ConnectionBanner, type ConnectionState } from './connection-banner'
import { NotificationEventCard } from './notification-event-card'
import { PushPermissionCard } from './push-permission-card'
import { PushDeviceControls, type PushDeviceControlState } from './push-device-controls'
import { SyncIndicator } from './sync-indicator'
import { UpdatePrompt } from './update-prompt'

const meta = { title: 'Product/Connectivity', parameters: { layout: 'padded' } } satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

const banners: { state: ConnectionState; actionImpact?: string; queuedCount?: number }[] = [
  { state: 'online' },
  { state: 'syncing' },
  {
    state: 'offline',
    actionImpact: 'Отправка недоступна. Решение сохранится и уйдёт, когда вернётся сеть.',
    queuedCount: 2,
  },
  { state: 'reconnecting', actionImpact: 'Пробуем отправить последнюю работу ещё раз.' },
  {
    state: 'conflict',
    actionImpact: 'Пока вы писали вердикт, работу обновили. Обновите состояние перед отправкой.',
  },
]

export const Connection: Story = {
  name: 'Состояния связи',
  render: () => (
    <div className="max-w-md space-y-3">
      {banners.map((banner) => (
        <ConnectionBanner
          actionImpact={banner.actionImpact}
          key={banner.state}
          onOpenOutbox={() => undefined}
          onResolve={() => undefined}
          queuedCount={banner.queuedCount}
          state={banner.state}
        />
      ))}
    </div>
  ),
}

export const Sync: Story = {
  name: 'Очередь отправки',
  render: () => {
    function Harness() {
      const [opened, setOpened] = useState(false)
      return (
        <div className="max-w-md space-y-3">
          <SyncIndicator onOpenOutbox={() => setOpened(true)} queuedCount={3} />
          <SyncIndicator queuedCount={0} />
          <SyncIndicator queuedCount={1} syncing />
          <p className="text-small text-muted-foreground" data-testid="readout" role="status">
            {opened ? 'Открыта очередь отправки' : 'Очередь закрыта'}
          </p>
        </div>
      )
    }
    return <Harness />
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.click(canvas.getByRole('button', { name: 'В очереди: 3' }))
    await expect(canvas.getByTestId('readout')).toHaveTextContent('Открыта очередь отправки')
  },
}

export const Update: Story = {
  name: 'Обновление без потери черновика',
  render: () => {
    function Harness() {
      const [updated, setUpdated] = useState(false)
      return (
        <div className="max-w-md space-y-3">
          <UpdatePrompt onDismiss={() => undefined} onUpdate={() => setUpdated(true)} />
          <p className="text-small text-muted-foreground" data-testid="readout" role="status">
            {updated ? 'Обновление запущено' : 'Ожидает'}
          </p>
        </div>
      )
    }
    return <Harness />
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.click(canvas.getByRole('button', { name: 'Обновить' }))
    await expect(canvas.getByTestId('readout')).toHaveTextContent('Обновление запущено')
  },
}

export const Push: Story = {
  name: 'Разрешение на уведомления',
  render: () => {
    function Harness() {
      const [state, setState] = useState<'idle' | 'enabled' | 'dismissed'>('idle')
      return (
        <div className="max-w-md space-y-3">
          <PushPermissionCard
            categories={[
              { id: 'result', label: 'Результат проверки', description: 'когда работу проверили' },
              { id: 'deadline', label: 'Скоро дедлайн', description: 'за день до закрытия приёма' },
              { id: 'news', label: 'Новости кружка' },
            ]}
            onDismiss={() => setState('dismissed')}
            onEnable={() => setState('enabled')}
          />
          <p className="text-small text-muted-foreground" data-testid="readout" role="status">
            {state === 'enabled'
              ? 'Запросим разрешение у браузера'
              : state === 'dismissed'
                ? 'Отказ принят'
                : 'Ожидает решения'}
          </p>
        </div>
      )
    }
    return <Harness />
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.click(canvas.getByRole('button', { name: 'Включить уведомления' }))
    await expect(canvas.getByTestId('readout')).toHaveTextContent('Запросим разрешение у браузера')
  },
}

const pushStates: PushDeviceControlState[] = [
  'loading',
  'available',
  'enabled',
  'denied',
  'unsupported',
  'error',
]

export const PushDeviceStates: Story = {
  name: 'Push · состояния устройства',
  render: () => (
    <div className="grid max-w-3xl gap-4 md:grid-cols-2">
      {pushStates.map((state) => (
        <section className="space-y-2" key={state}>
          <p className="text-caption text-muted-foreground">{state}</p>
          <PushDeviceControls
            categories={[{ id: 'news', label: 'Новости кружка' }]}
            onDisable={() => undefined}
            onDismiss={() => undefined}
            onEnable={() => undefined}
            state={state}
          />
        </section>
      ))}
    </div>
  ),
}

export const InAppEvents: Story = {
  name: 'In-app события · новое и прочитанное',
  render: () => (
    <div className="max-w-lg space-y-2">
      <NotificationEventCard
        description="Математика · Начинающие · аудитория 202"
        href="/student/"
        occurredAt="5 октября, 15:00"
        occurredAtDateTime="2026-10-05T12:00:00Z"
        title="Назначена аудитория"
        unread
      />
      <NotificationEventCard
        description="Проверены три письменные задачи"
        occurredAt="4 октября, 18:30"
        occurredAtDateTime="2026-10-04T15:30:00Z"
        title="Проверка завершена"
      />
    </div>
  ),
}
