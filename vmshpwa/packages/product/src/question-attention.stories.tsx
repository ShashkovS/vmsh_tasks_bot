import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, within } from 'storybook/test'
import { Button } from '@vmsh/ui'
import { QuestionAttentionDot } from './question-attention'

const meta = { title: 'Product/QuestionAttention', component: QuestionAttentionDot } satisfies Meta<
  typeof QuestionAttentionDot
>
export default meta
type Story = StoryObj<typeof meta>
export const Waiting: Story = {
  args: { state: 'awaiting_reply' },
  render: (args) => (
    <Button variant="ghost">
      Вопросы по задаче <QuestionAttentionDot {...args} />
    </Button>
  ),
  play: async ({ canvasElement }) => {
    await expect(
      within(canvasElement).getByRole('button', { name: /Ждём ответа преподавателя/ }),
    ).toBeVisible()
  },
}
export const Unread: Story = {
  ...Waiting,
  args: { state: 'unread_reply' },
  play: async ({ canvasElement }) => {
    await expect(
      within(canvasElement).getByRole('button', { name: /Есть непрочитанный ответ/ }),
    ).toBeVisible()
  },
}
export const Read: Story = {
  ...Waiting,
  args: { state: 'none' },
  play: async ({ canvasElement }) => {
    await expect(
      within(canvasElement).getByRole('button', { name: /^Вопросы по задаче$/ }),
    ).toBeVisible()
  },
}
