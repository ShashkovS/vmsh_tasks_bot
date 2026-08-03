import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import moderationFixture from '@vmsh/contracts/fixtures/news/moderation.v1.json'
import {
  staffNewsItemSchema,
  staffNewsListResponseSchema,
  type StaffNewsItem,
} from '@vmsh/contracts'

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

function EditableScheduledModeration({ items }: { items: StaffNewsItem[] }) {
  const [edited, setEdited] = useState(false)
  return (
    <div className="space-y-3">
      <NewsModerationList items={items} onEdit={() => setEdited(true)} />
      {edited ? <p role="status">Открыт редактор публикации</p> : null}
    </div>
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

export const ScheduledLocal: Story = {
  name: 'Локальная публикация по расписанию',
  args: {
    items: [
      staffNewsItemSchema.parse({
        postId: 'news.local-scheduled',
        source: 'local',
        channelTitle: null,
        ownerType: 'group',
        ownerId: 'group.beginner',
        ownerName: 'Начинающие',
        publishedAt: '2099-08-04T14:00:00Z',
        editedAt: null,
        revision: 1,
        textExcerpt: 'Разбор задач состоится завтра в 17:00.',
        editableText: 'Разбор задач состоится завтра в 17:00.',
        mediaCount: 0,
        visibility: 'visible',
        moderationReason: null,
        visibilityUpdatedAt: '2026-08-03T12:00:00Z',
        isScheduled: true,
        version: 1,
      }),
    ],
  },
  render: (args) => <EditableScheduledModeration items={args.items} />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByText('По расписанию')).toBeInTheDocument()
    await userEvent.click(canvas.getByRole('button', { name: /Изменить запланированную/ }))
    await expect(canvas.getByRole('status')).toHaveTextContent('Открыт редактор публикации')
  },
}
