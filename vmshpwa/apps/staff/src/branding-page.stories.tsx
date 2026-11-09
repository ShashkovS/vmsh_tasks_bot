import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, fn, userEvent, within } from 'storybook/test'
import { BrandingSettingsView } from './branding-page'
const meta = {
  title: 'Pages/Staff/Branding',
  component: BrandingSettingsView,
  args: { current: { profileId: 'vmsh', version: 1 }, saving: false, onSave: fn() },
} satisfies Meta<typeof BrandingSettingsView>
export default meta
type Story = StoryObj<typeof meta>
export const Default: Story = {}
export const Dark: Story = { globals: { theme: 'dark' } }
export const Saving: Story = { args: { saving: true } }
export const Error: Story = {
  args: { error: 'Не удалось сохранить оформление. Попробуйте снова.' },
}
export const SelectTlf: Story = {
  play: async ({ canvasElement, args }) => {
    const canvas = within(canvasElement)
    await userEvent.click(canvas.getByRole('radio', { name: 'TLF Prep Clubs' }))
    await userEvent.click(canvas.getByRole('button', { name: 'Применить' }))
    await expect(args.onSave).toHaveBeenCalledWith({ profileId: 'tlf-prep-clubs', version: 1 })
  },
}
