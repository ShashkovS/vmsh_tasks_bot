import { useState } from 'react'
import { cleanup, fireEvent, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { renderWithI18n as render } from '@vmsh/test-utils/i18n'
import { ReviewFeedbackForm, fullVerdictScale, type ReviewFeedbackDraft } from '@vmsh/product'
import { aiReviewSuggestionSchema, type AiReviewSuggestion } from '@vmsh/contracts'
import { AiReviewSuggestionsView } from './ai-review-suggestions-view'
import { applyAiSuggestion } from './ai-review-model'

afterEach(cleanup)
const suggestion: AiReviewSuggestion = {
  suggestionId: 'ais-1',
  snapshot: 'a'.repeat(64),
  source: 'Model A',
  model: 'test/model',
  createdAt: '2026-10-18T12:00:00Z',
  isCurrent: true,
  comment: 'Поясните последний переход.',
  verdict: 14,
  analysis: 'PRIVATE: internal reasoning',
}
const initial: ReviewFeedbackDraft = {
  comment: 'Мой комментарий',
  verdictValue: 'plus',
  reactionId: 100,
}

it('appends only text and separately chooses a verdict from another model', () => {
  const text = applyAiSuggestion(initial, suggestion, 'comment')
  expect(text).toEqual({ ...initial, comment: 'Мой комментарий\n\nПоясните последний переход.' })
  const verdict = applyAiSuggestion(
    text,
    { ...suggestion, source: 'Model B', verdict: 11 },
    'verdict',
  )
  expect(verdict).toEqual({ ...text, verdictValue: 'rejected' })
  expect(verdict.comment).not.toContain('PRIVATE')
})

it('updates a controlled form without remounting or sending the review', () => {
  const submit = vi.fn()
  function Harness() {
    const [draft, setDraft] = useState(initial)
    return (
      <>
        <AiReviewSuggestionsView
          items={[suggestion]}
          currentWork
          onApply={(item, field) => setDraft(applyAiSuggestion(draft, item, field))}
        />
        <ReviewFeedbackForm
          draft={draft}
          verdicts={fullVerdictScale}
          onDraftChange={setDraft}
          onSubmit={submit}
        />
      </>
    )
  }
  render(<Harness />)
  fireEvent.click(screen.getByRole('button', { name: 'Добавить комментарий' }))
  expect(screen.getByRole<HTMLTextAreaElement>('textbox', { name: 'Комментарий' }).value).toBe(
    'Мой комментарий\n\nПоясните последний переход.',
  )
  expect(submit).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Выбрать вердикт' }))
  expect(submit).not.toHaveBeenCalled()
  fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Отредактировано учителем' } })
  fireEvent.click(screen.getByRole('button', { name: 'Отправить вердикт' }))
  expect(submit).toHaveBeenCalledWith(
    expect.objectContaining({
      comment: 'Отредактировано учителем',
      verdict: expect.objectContaining({ value: 'half' }),
    }),
  )
})

it('keeps stale and mismatched suggestions readable but not applicable', () => {
  const apply = vi.fn()
  render(
    <AiReviewSuggestionsView
      items={[suggestion, { ...suggestion, suggestionId: 'ais-2', isCurrent: false }]}
      currentWork={false}
      onApply={apply}
    />,
  )
  for (const button of screen.getAllByRole('button'))
    expect((button as HTMLButtonElement).disabled).toBe(true)
  expect(
    screen.getAllByText('Предложение устарело или материалы требуют обновления.'),
  ).toHaveLength(2)
  expect(apply).not.toHaveBeenCalled()
})

it('escapes model text and rejects invalid verdict payloads', () => {
  const { container } = render(
    <AiReviewSuggestionsView
      items={[{ ...suggestion, comment: '<script>alert(1)</script>' }]}
      currentWork
      onApply={vi.fn()}
    />,
  )
  expect(container.querySelector('script')).toBeNull()
  expect(screen.getByText('<script>alert(1)</script>')).toBeTruthy()
  expect(aiReviewSuggestionSchema.safeParse({ ...suggestion, verdict: 100 }).success).toBe(false)
})

it('renders no panel for absent proposals', () => {
  const { container } = render(<AiReviewSuggestionsView items={[]} currentWork onApply={vi.fn()} />)
  expect(container.innerHTML).toBe('')
})
