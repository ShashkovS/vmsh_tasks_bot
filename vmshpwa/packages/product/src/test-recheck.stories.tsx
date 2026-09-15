import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import { TestAttemptRecheckPanel } from './test-attempt-recheck'

const meta = {
  title: 'Product/Test answer',
  component: TestAttemptRecheckPanel,
  parameters: { layout: 'padded' },
  decorators: [
    (Story) => (
      <div className="max-w-2xl">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof TestAttemptRecheckPanel>

export default meta
type Story = StoryObj<typeof meta>

function PendingHarness() {
  const [applied, setApplied] = useState(false)
  return (
    <TestAttemptRecheckPanel
      onApply={() => setApplied(true)}
      pendingAttempts={applied ? 0 : 4}
      problemRevision={{ conditionRevisionId: 'condition-revision-42', configVersion: 3 }}
      {...(applied
        ? {
            result: {
              pendingBefore: 4,
              checked: 4,
              correct: 3,
              wrong: 1,
              stillPending: 0,
              skippedConcurrent: 0,
            },
          }
        : {})}
    />
  )
}

export const RecheckPending: Story = {
  name: 'Перепроверка отложенных ответов',
  render: () => <PendingHarness />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.click(canvas.getByRole('button', { name: 'Перепроверить 4 ответа' }))
    await expect(canvas.getByText('Проверено 4 из 4')).toBeInTheDocument()
    await expect(canvas.getByText('Нет ответов, ожидающих настройки')).toBeInTheDocument()
  },
}

export const RecheckStillPending: Story = {
  name: 'Checker всё ещё требует исправления',
  args: {
    pendingAttempts: 2,
    problemRevision: { conditionRevisionId: 'condition-revision-42', configVersion: 4 },
    result: {
      pendingBefore: 3,
      checked: 1,
      correct: 1,
      wrong: 0,
      stillPending: 2,
      skippedConcurrent: 0,
    },
    onApply: () => undefined,
  },
}

export const RecheckConflict: Story = {
  name: 'Версия изменилась перед запуском',
  args: {
    pendingAttempts: 4,
    problemRevision: { conditionRevisionId: 'condition-revision-42', configVersion: 3 },
    error: 'Опубликована новая версия задачи. Обновите данные и проверьте действие ещё раз.',
    onApply: () => undefined,
    onRetry: () => undefined,
  },
}

export const RecheckLoading: Story = {
  name: 'Загрузка состояния',
  args: { loading: true },
}
