import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, userEvent, within } from 'storybook/test'
import { PasteEvidenceBadge } from './paste-evidence-badge'

const meta = { title: 'Product/Paste evidence', component: PasteEvidenceBadge } satisfies Meta<
  typeof PasteEvidenceBadge
>
export default meta
type Story = StoryObj<typeof meta>

export const Levels: Story = {
  render: () => (
    <div className="flex flex-wrap gap-3">
      {[0, 1, 24, 25, 74, 75, 100].map((percentage) => (
        <PasteEvidenceBadge key={percentage} estimate={{ percentage, method: 'remaining_text' }} />
      ))}
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.queryByText('Вставлено ≈ 0%')).not.toBeInTheDocument()
    await expect(canvas.getByText('Вставлено ≈ 100%')).toBeVisible()
    await userEvent.click(canvas.getByText('Вставлено ≈ 25%'))
    await expect(within(document.body).getByRole('tooltip')).toHaveTextContent(
      'Не определяет использование ИИ.',
    )
  },
}

export const Historical: Story = {
  args: { estimate: { percentage: 42, method: 'cumulative_pastes' } },
  play: async ({ canvasElement }) => {
    await userEvent.click(within(canvasElement).getByText('Вставлено ≈ 42%'))
    await expect(within(document.body).getByRole('tooltip')).toHaveTextContent(
      'не учитывает последующие удаления',
    )
  },
}

export const Unknown: Story = { args: { estimate: null } }
