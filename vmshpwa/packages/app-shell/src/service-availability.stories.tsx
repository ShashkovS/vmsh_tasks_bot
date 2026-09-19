import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, within } from 'storybook/test'
import { ServiceAvailabilityBannerView } from './service-availability'

const meta = {
  title: 'App shell/Service recovery',
  component: ServiceAvailabilityBannerView,
  args: { state: { state: 'updating', since: 1, prolonged: false } },
} satisfies Meta<typeof ServiceAvailabilityBannerView>
export default meta
type Story = StoryObj<typeof meta>

export const Updating: Story = {
  play: async ({ canvasElement }) => {
    await expect(within(canvasElement).getByRole('status')).toHaveTextContent('Обновляем сервис')
    await expect(within(canvasElement).queryByRole('alert')).not.toBeInTheDocument()
  },
}
export const Prolonged: Story = {
  args: { state: { state: 'updating', since: 1, prolonged: true } },
  play: async ({ canvasElement }) => {
    await expect(within(canvasElement).getByRole('status')).toHaveTextContent(
      'Мы продолжаем подключаться',
    )
  },
}
export const Reconnecting: Story = {
  args: { state: { state: 'reconnecting', since: 1, prolonged: false } },
}
