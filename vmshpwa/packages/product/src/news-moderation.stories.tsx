import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import moderationFixture from '@vmsh/contracts/fixtures/news/moderation.v1.json'
import { staffNewsListResponseSchema, type StaffNewsItem } from '@vmsh/contracts'

import { NewsModerationList } from './news-moderation'

const items = staffNewsListResponseSchema.parse(moderationFixture).items

const meta = {
  title: 'Product/News moderation',
  component: NewsModerationList,
  parameters: { layout: 'padded' },
} satisfies Meta<typeof NewsModerationList>
export default meta
type Story = StoryObj<typeof meta>

function InteractiveModeration() {
  const [current, setCurrent] = useState(items)
  const change = (target: StaffNewsItem, visibility: StaffNewsItem['visibility']) =>
    setCurrent((previous) =>
      previous.map((item) =>
        item.postId === target.postId
          ? { ...item, visibility, version: item.version + 1, moderationReason: null }
          : item,
      ),
    )
  return (
    <NewsModerationList
      items={current}
      onHide={(item) => change(item, 'manual_hidden')}
      onMarkSourceDeleted={(item) => change(item, 'source_deleted')}
      onMarkSourcePresent={(item) => change(item, 'visible')}
      onRestore={(item) => change(item, 'visible')}
    />
  )
}

export const Lifecycle: Story = {
  name: 'В ленте, скрыто и удалено в источнике',
  args: { items },
  render: () => <InteractiveModeration />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const visiblePost = canvas.getByText('Опубликованы условия занятия.').closest('li')
    if (!visiblePost) throw new Error('Visible post row was not rendered')

    await userEvent.click(within(visiblePost).getByRole('button', { name: /Скрыть публикацию/ }))
    await expect(within(visiblePost).getByText('Скрыто в PWA')).toBeInTheDocument()
    await userEvent.click(within(visiblePost).getByRole('button', { name: /Вернуть публикацию/ }))
    await expect(within(visiblePost).getByText('В ленте')).toBeInTheDocument()
    await userEvent.click(
      within(visiblePost).getByRole('button', { name: /Отметить публикацию .* удалённой/ }),
    )
    await expect(within(visiblePost).getByText('Удалено в Telegram')).toBeInTheDocument()
    await userEvent.click(
      within(visiblePost).getByRole('button', { name: /Отметить публикацию .* доступной/ }),
    )
    await expect(within(visiblePost).getByText('В ленте')).toBeInTheDocument()
  },
}
