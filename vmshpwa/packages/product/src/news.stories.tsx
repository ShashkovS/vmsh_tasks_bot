import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, userEvent, within } from 'storybook/test'

import type {
  TelegramEntity,
  TelegramEntityType,
  TelegramMedia,
  TelegramPostView,
} from './telegram-post'
import { TelegramRichPost } from './telegram-rich-post'

const meta = { title: 'Product/News', parameters: { layout: 'padded' } } satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

function ent(text: string, sub: string, type: TelegramEntityType, href?: string): TelegramEntity {
  const offset = text.indexOf(sub)
  return href === undefined
    ? { type, offset, length: sub.length }
    : { type, offset, length: sub.length, href }
}

const body = 'В субботу пробное занятие. Регистрация на сайте кружка. Ответ к задаче 6: 89.'
const entities: TelegramEntity[] = [
  ent(body, 'пробное занятие', 'bold'),
  ent(body, 'на сайте кружка', 'link', 'https://example.org'),
  ent(body, '89', 'spoiler'),
]

const media: TelegramMedia[] = [
  { kind: 'photo', alt: 'Фото занятия' },
  { kind: 'photo', alt: 'Доска с задачей' },
  { kind: 'video', durationLabel: '1:20', alt: 'Разбор задачи' },
  { kind: 'document', name: 'Листок 21н.pdf', sizeLabel: '240 КБ' },
]

const post: TelegramPostView = {
  id: 'p1',
  attribution: { channel: 'ВМШ 179' },
  blocks: [
    { kind: 'text', text: body, entities },
    { kind: 'quote', text: '«Математика — гимнастика ума».' },
    { kind: 'math', html: 'n^2 + 179 = k^2' },
  ],
  media,
  at: '24 января, 18:00',
}

const renderMath = (html: string) => (
  <span className="rounded bg-surface-sunken px-1 font-mono text-[0.9em]">{html}</span>
)

export const Post: Story = {
  name: 'Пост с разметкой и медиа',
  render: () => (
    <div className="max-w-md">
      <TelegramRichPost post={post} renderMath={renderMath} />
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)

    await expect(canvas.getByText('пробное занятие').tagName).toBe('STRONG')
    await expect(canvas.getByRole('link', { name: 'на сайте кружка' })).toBeInTheDocument()

    // Спойлер раскрывается по клику.
    const spoiler = canvas.getByRole('button', { name: 'Показать скрытый текст' })
    await userEvent.click(spoiler)
    await expect(
      canvas.queryByRole('button', { name: 'Показать скрытый текст' }),
    ).not.toBeInTheDocument()
  },
}

export const Previews: Story = {
  name: 'Превью: PWA и Telegram',
  render: () => (
    <div className="grid max-w-3xl gap-4 sm:grid-cols-2">
      <div className="space-y-1">
        <p className="text-caption text-muted-foreground">Как в приложении</p>
        <TelegramRichPost post={post} renderMath={renderMath} surface="pwa" />
      </div>
      <div className="space-y-1">
        <p className="text-caption text-muted-foreground">Как в Telegram</p>
        <TelegramRichPost post={post} renderMath={renderMath} surface="telegram" />
      </div>
    </div>
  ),
}

export const Card: Story = {
  name: 'Компактная карточка (лента)',
  render: () => (
    <div className="max-w-md">
      <TelegramRichPost post={post} renderMath={renderMath} variant="card" />
    </div>
  ),
}

const states: { label: string; post: TelegramPostView }[] = [
  {
    label: 'Изменено в источнике',
    post: { ...post, media: undefined, state: 'source-revised', editedAt: '25 января, 09:10' },
  },
  {
    label: 'Локальная правка',
    post: { ...post, media: undefined, state: 'local-override' },
  },
  {
    label: 'Удалено в источнике',
    post: { ...post, media: undefined, state: 'source-deleted' },
  },
  {
    label: 'Ошибка доставки',
    post: { ...post, media: undefined, state: 'delivery-error' },
  },
  {
    label: 'Скрыто редакцией',
    post: { ...post, media: undefined, state: 'hidden' },
  },
]

export const States: Story = {
  name: 'Редакционные состояния',
  render: () => (
    <div className="max-w-md space-y-4">
      {states.map(({ label, post: statePost }) => (
        <div className="space-y-1" key={label}>
          <p className="text-caption text-muted-foreground">{label}</p>
          <TelegramRichPost
            onRetryDelivery={() => undefined}
            post={statePost}
            renderMath={renderMath}
          />
        </div>
      ))}
    </div>
  ),
}
