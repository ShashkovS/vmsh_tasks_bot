import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, userEvent, within } from 'storybook/test'

import type { TelegramEntity, TelegramEntityType, TelegramPostView } from './telegram-post'
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

const body = 'Условия 38-го занятия для начинающих. Приём решений открыт до воскресенья, 13:00.'
const entities: TelegramEntity[] = [
  ent(body, 'Условия 38-го занятия', 'bold'),
  ent(body, 'до воскресенья, 13:00', 'underline'),
]

const post: TelegramPostView = {
  id: 'p1',
  attribution: { channel: 'ВМШ 179' },
  blocks: [
    { kind: 'heading', level: 2, text: 'Задачи 38-го занятия' },
    { kind: 'text', text: body, entities },
    { kind: 'heading', level: 3, text: '38н.6. Расстановка ладей' },
    {
      kind: 'text',
      text: 'На доске n × n расставляют ладьи так, чтобы никакие две не били друг друга. Найдите число способов расставить ровно k ладей.',
    },
    { kind: 'math', html: '\\binom{n}{k}^2 \\cdot k!' },
    {
      kind: 'list',
      ordered: true,
      items: [
        { text: 'Разберите случай k = 1.' },
        { text: 'Разберите случай k = n.' },
        { text: 'Объясните общий ответ.' },
      ],
    },
    {
      kind: 'details',
      summary: 'Подсказка',
      blocks: [
        {
          kind: 'text',
          text: 'Сначала выберите строки и столбцы, затем сопоставьте их.',
        },
      ],
    },
    { kind: 'divider' },
    {
      kind: 'text',
      text: '#условия #начинающие #38занятие',
      entities: [
        ent(
          '#условия #начинающие #38занятие',
          '#38занятие',
          'link',
          'https://t.me/vmsh_179_5_7_2025',
        ),
      ],
    },
  ],
  at: '24 января, 18:00',
}

const renderMath = (html: string) => (
  <span className="rounded bg-surface-sunken px-1 font-mono text-[0.9em]">{html}</span>
)

export const Post: Story = {
  name: 'Полное условие текстом в Telegram Rich Message',
  render: () => (
    <div className="max-w-md">
      <TelegramRichPost post={post} renderMath={renderMath} />
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)

    await expect(canvas.getByText('Задачи 38-го занятия').tagName).toBe('H2')
    await expect(canvas.getByText('38н.6. Расстановка ладей').tagName).toBe('H3')
    await expect(canvas.getByText(/никакие две не били/)).toBeInTheDocument()
    await userEvent.click(canvas.getByText('Подсказка'))
    await expect(canvas.getByText(/выберите строки и столбцы/)).toBeInTheDocument()
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
