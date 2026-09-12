import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import preferencesFixture from '@vmsh/contracts/fixtures/notifications/preferences.v1.json'
import {
  notificationEventSchema,
  notificationPreferenceListResponseSchema,
  type NotificationPreference,
} from '@vmsh/contracts'
import { PushDeviceControls } from '@vmsh/product'

import { FamilyNotificationSettingsView } from './family-notifications-page'

const preferences = notificationPreferenceListResponseSchema.parse(preferencesFixture).items
const digestEvent = notificationEventSchema.parse({
  eventId: 'notification.family-digest.41',
  category: 'review_completed',
  route: '/family/children/student.one',
  payload: {
    kind: 'family_lesson_digest',
    groupName: 'Начинающие',
    lessonNumber: 41,
  },
  occurredAt: '2026-10-05T12:00:00Z',
  deliverAfter: '2026-10-05T12:00:00Z',
  readAt: null,
})

const meta = {
  title: 'Pages/Family/Notifications',
  component: FamilyNotificationSettingsView,
  parameters: { canvasPadding: false, layout: 'fullscreen' },
} satisfies Meta<typeof FamilyNotificationSettingsView>
export default meta
type Story = StoryObj<typeof meta>

function ReadyView() {
  const [items, setItems] = useState(preferences)
  const [changed, setChanged] = useState('Нет изменений')
  const toggle = (preference: NotificationPreference, pushEnabled: boolean) => {
    setItems((current) =>
      current.map((item) =>
        item.category === preference.category ? { ...item, pushEnabled } : item,
      ),
    )
    setChanged(`${preference.category}:${String(pushEnabled)}`)
  }
  return (
    <>
      <FamilyNotificationSettingsView
        events={[digestEvent]}
        onToggle={toggle}
        preferences={items}
        pushControls={
          <PushDeviceControls
            categories={[{ id: 'news', label: 'Новости кружка' }]}
            onDisable={() => undefined}
            onDismiss={() => undefined}
            onEnable={() => undefined}
            state="enabled"
          />
        }
      />
      <p className="sr-only" data-testid="changed" role="status">
        {changed}
      </p>
    </>
  )
}

export const Ready: Story = {
  render: () => <ReadyView />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getAllByRole('switch')).toHaveLength(6)
    await expect(canvas.getByText('Итоги занятия готовы')).toBeVisible()
    await expect(canvas.getByLabelText('Push: Итоги занятия')).toBeVisible()
    await expect(canvas.queryByLabelText(/Назначена аудитория/)).not.toBeInTheDocument()
    await userEvent.click(canvas.getByRole('switch', { name: 'Push: Новости' }))
    await expect(canvas.getByTestId('changed')).toHaveTextContent('news:false')
  },
}

export const Loading: Story = { args: { loading: true } }

export const Error: Story = {
  args: { error: true, onRetry: () => undefined },
  play: async ({ canvasElement }) => {
    await expect(within(canvasElement).getByRole('button', { name: 'Повторить' })).toBeVisible()
  },
}

export const PushDenied: Story = {
  args: {
    preferences,
    pushControls: (
      <PushDeviceControls
        categories={[]}
        onDisable={() => undefined}
        onDismiss={() => undefined}
        onEnable={() => undefined}
        state="denied"
      />
    ),
  },
}
