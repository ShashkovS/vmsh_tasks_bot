import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, userEvent, within } from 'storybook/test'

import fixture from '@vmsh/contracts/fixtures/group-banners/list.v1.json'
import { groupBannerListResponseSchema } from '@vmsh/contracts'

import { GroupBanner } from './group-banner'

const banners = groupBannerListResponseSchema.parse(fixture).items

const meta = {
  title: 'Product/News/Group banner',
  component: GroupBanner,
  parameters: { layout: 'padded' },
} satisfies Meta<typeof GroupBanner>
export default meta
type Story = StoryObj<typeof meta>

export const ScheduledAndDismissible: Story = {
  args: { banner: banners[0]!, onDismiss: () => undefined },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByText('Разбор сегодня в 17:00')).toBeInTheDocument()
    await expect(canvas.getByRole('link', { name: 'Подключиться' })).toHaveAttribute(
      'href',
      'https://example.test',
    )
    await userEvent.click(canvas.getByRole('button', { name: 'Скрыть объявление' }))
  },
}

export const PersistentReminder: Story = { args: { banner: banners[1]! } }
