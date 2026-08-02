import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import deliveryBatchFixture from '@vmsh/contracts/fixtures/classrooms/delivery-batch.v1.json'
import deliveryPreviewFixture from '@vmsh/contracts/fixtures/classrooms/delivery-preview.v1.json'
import {
  classroomDeliveryBatchResponseSchema,
  classroomDeliveryPreviewResponseSchema,
  type ClassroomDeliveryBatch,
} from '@vmsh/contracts'

import { ClassroomDeliveryPanel } from './classroom-delivery'

const preview = classroomDeliveryPreviewResponseSchema.parse(deliveryPreviewFixture).preview
const batch = classroomDeliveryBatchResponseSchema.parse(deliveryBatchFixture).batch

const meta = {
  title: 'Product/Classrooms',
  component: ClassroomDeliveryPanel,
  globals: { density: 'staff' },
  parameters: { layout: 'padded' },
} satisfies Meta<typeof ClassroomDeliveryPanel>

export default meta
type Story = StoryObj<typeof meta>

function PreviewHarness() {
  const [sentChannels, setSentChannels] = useState('')
  return (
    <div className="space-y-2">
      <ClassroomDeliveryPanel
        onSend={(channels) => setSentChannels(channels.join(', '))}
        preview={preview}
      />
      <p className="text-caption text-muted-foreground" data-testid="delivery-readout">
        {sentChannels || 'Рассылка не запускалась'}
      </p>
    </div>
  )
}

export const DeliveryPreview: Story = {
  name: 'Рассылка · безопасный preview и выбор каналов',
  render: () => <PreviewHarness />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.click(canvas.getByText('Проверить получателей (3)'))
    await expect(canvas.getByText('Белова Анна')).toBeInTheDocument()
    await userEvent.click(canvas.getByRole('checkbox', { name: /Telegram/ }))
    await userEvent.click(canvas.getByRole('button', { name: 'Разослать аудитории' }))
    await expect(canvas.getByTestId('delivery-readout')).toHaveTextContent('pwa')
  },
}

export const DeliveryChangedAfterSend: Story = {
  name: 'Рассылка · план изменён после отправки',
  args: {
    batch,
    changedAfterSend: true,
    onPreview: () => undefined,
  },
}

const partialBatch: ClassroomDeliveryBatch = {
  ...batch,
  state: 'completed_with_errors',
  completedAt: '2026-02-01T07:02:00Z',
  channelCounts: {
    pwa: { sent: 3 },
    telegram: { sent: 1, failed: 1, suppressed: 1 },
  },
  deliveryReport: {
    channels: {
      pwa: {
        selected: 3,
        eligible: 3,
        suppressed: 0,
        queued: 0,
        attempted: 3,
        succeeded: 3,
        failed: 0,
      },
      telegram: {
        selected: 3,
        eligible: 2,
        suppressed: 1,
        queued: 0,
        attempted: 2,
        succeeded: 1,
        failed: 1,
      },
    },
    deliveredAny: 3,
    deliveredAll: 1,
    partial: 2,
  },
  recipients: batch.recipients.map((recipient, index) =>
    index === 1
      ? {
          ...recipient,
          telegram: { state: 'failed', errorCode: 'telegram_forbidden', sentAt: null },
        }
      : index === 0
        ? {
            ...recipient,
            telegram: {
              state: 'sent',
              errorCode: null,
              sentAt: '2026-02-01T07:01:00Z',
            },
          }
        : recipient,
  ),
}

export const DeliveryPartialReport: Story = {
  name: 'Рассылка · частичный результат по каналам',
  args: { batch: partialBatch },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByText('Получили хотя бы одно: 3')).toBeInTheDocument()
    await expect(canvas.getByText('Получили всё: 1')).toBeInTheDocument()
    await userEvent.click(canvas.getByText('Частично доставлено (2)'))
    const partial = within(canvas.getByTestId('partial-recipient-list'))
    await expect(partial.getByText('Ветров Борис')).toBeInTheDocument()
    await expect(partial.getByText(/Telegram: ошибка/)).toBeInTheDocument()
    await expect(partial.getByText('Орлова Вера')).toBeInTheDocument()
    await expect(partial.getByText(/Telegram: недоступно/)).toBeInTheDocument()
  },
}

function RetryHarness() {
  const [retried, setRetried] = useState(false)
  return (
    <div className="space-y-2">
      <ClassroomDeliveryPanel batch={partialBatch} onRetryFailed={() => setRetried(true)} />
      <p className="text-caption text-muted-foreground" role="status">
        {retried ? 'Повтор поставлен в очередь' : 'Повтор не запускался'}
      </p>
    </div>
  )
}

export const DeliveryRetryFailed: Story = {
  name: 'Рассылка · повтор только ошибок',
  render: () => <RetryHarness />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.click(canvas.getByRole('button', { name: 'Повторить только ошибки' }))
    await expect(canvas.getByRole('status')).toHaveTextContent('Повтор поставлен в очередь')
  },
}
