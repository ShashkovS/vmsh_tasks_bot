import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, within } from 'storybook/test'

import { LandingPage } from './landing-page'

const meta = {
  title: 'Product/Landing',
  component: LandingPage,
  parameters: { canvasPadding: false, layout: 'fullscreen' },
} satisfies Meta<typeof LandingPage>

export default meta
type Story = StoryObj<typeof meta>

export const Home: Story = {
  name: 'Home',
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const links = canvas.getAllByRole('link', { name: 'Открыть кабинет' })
    await expect(links[0]).toHaveAttribute('href', '/student/')
    await expect(links[1]).toHaveAttribute('href', '/family/')
    await expect(canvas.queryByText(/staff|учител/i)).not.toBeInTheDocument()
  },
}

export const MobileLight: Story = {
  name: 'Mobile · светлая',
  parameters: { viewport: { defaultViewport: 'mobile1' } },
}

export const DesktopLight: Story = {
  name: 'Desktop · светлая',
  parameters: { viewport: { defaultViewport: 'desktop' } },
}
