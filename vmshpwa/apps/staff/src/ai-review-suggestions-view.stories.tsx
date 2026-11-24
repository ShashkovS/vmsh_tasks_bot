import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'
import type { AiReviewSuggestion } from '@vmsh/contracts'
import { ReviewFeedbackForm, fullVerdictScale, type ReviewFeedbackDraft } from '@vmsh/product'
import { AiReviewSuggestionsView } from './ai-review-suggestions-view'
import { applyAiSuggestion } from './ai-review-model'

const proposal: AiReviewSuggestion = {
  suggestionId: 'ais-1',
  snapshot: 'a'.repeat(64),
  source: 'Внешняя проверка',
  model: 'model-a',
  createdAt: '2026-10-18T12:00:00Z',
  isCurrent: true,
  verdict: 14,
  comment: 'Объясните, почему во втором случае других вариантов нет.',
  analysis:
    'Первый случай разобран верно. Во втором случае пропущено обоснование полноты перебора.',
}
const meta = {
  title: 'Staff/AIReviewSuggestions',
  component: AiReviewSuggestionsView,
  args: { items: [proposal], currentWork: true, onApply: () => undefined },
  parameters: { layout: 'padded' },
} satisfies Meta<typeof AiReviewSuggestionsView>
export default meta
type Story = StoryObj<typeof meta>

function Harness() {
  const [draft, setDraft] = useState<ReviewFeedbackDraft>({
    comment: 'Верное начало.',
    verdictValue: 'plus',
    reactionId: null,
  })
  return (
    <div className="max-w-xl space-y-4">
      <AiReviewSuggestionsView
        items={[
          proposal,
          {
            ...proposal,
            suggestionId: 'ais-2',
            source: 'Другая модель',
            verdict: 17,
            comment: null,
          },
        ]}
        currentWork
        onApply={(item, field) => setDraft(applyAiSuggestion(draft, item, field))}
      />
      <ReviewFeedbackForm
        draft={draft}
        onDraftChange={setDraft}
        verdicts={fullVerdictScale}
        onSubmit={() => undefined}
      />
    </div>
  )
}
export const IndependentActions: Story = {
  render: () => <Harness />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.click(canvas.getByRole('button', { name: 'Добавить комментарий' }))
    await expect(canvas.getByRole('textbox')).toHaveValue(
      'Верное начало.\n\nОбъясните, почему во втором случае других вариантов нет.',
    )
    await userEvent.click(canvas.getAllByRole('button', { name: 'Выбрать вердикт' })[0]!)
    await expect(canvas.getByRole('textbox')).toHaveValue(
      'Верное начало.\n\nОбъясните, почему во втором случае других вариантов нет.',
    )
  },
}
export const Stale: Story = { args: { currentWork: false } }
export const Empty: Story = { args: { items: [] } }
export const AnalysisOnly: Story = {
  args: { items: [{ ...proposal, verdict: null, comment: null }] },
}
