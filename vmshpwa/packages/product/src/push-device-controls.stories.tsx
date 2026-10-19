import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, fn, userEvent, within } from 'storybook/test'
import { PushDeviceControls } from './push-device-controls'

const meta = {
  title: 'Product/Push device',
  component: PushDeviceControls,
  args: {
    state: 'available',
    categories: [{ id: 'news', label: 'Новости и учебные материалы' }],
    onEnable: fn(),
    onDisable: fn(),
    onDismiss: fn(),
  },
} satisfies Meta<typeof PushDeviceControls>
export default meta
type Story = StoryObj<typeof meta>
export const Available: Story = {}
export const Enabling: Story = { args: { state: 'enabling' } }
export const Enabled: Story = { args: { state: 'enabled' } }
export const InstallRequired: Story = { args: { state: 'install-required' } }
export const Denied: Story = { args: { state: 'denied' } }
export const Retry: Story = {
  args: { state: 'error' },
  play: async ({ canvasElement, args }) => {
    await userEvent.click(
      within(canvasElement).getByRole('button', { name: 'Включить уведомления' }),
    )
    await expect(args.onEnable).toHaveBeenCalled()
  },
}
