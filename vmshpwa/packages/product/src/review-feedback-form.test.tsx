import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ReviewFeedbackForm } from './review-feedback-form'
import { ternaryVerdictScale } from './verdict-registry'

afterEach(cleanup)
describe('review keyboard submission', () => {
  it('sends from the comment field and ignores the prepared disabled form', () => {
    const active = vi.fn(),
      hidden = vi.fn()
    render(
      <>
        <ReviewFeedbackForm
          verdicts={ternaryVerdictScale}
          onSubmit={active}
          initialDraft={{ verdictValue: 'plus', comment: '', reactionId: null }}
        />
        <ReviewFeedbackForm
          disabled
          verdicts={ternaryVerdictScale}
          onSubmit={hidden}
          initialDraft={{ verdictValue: 'plus', comment: '', reactionId: null }}
        />
      </>,
    )
    screen.getAllByRole('textbox')[0]!.focus()
    fireEvent.keyDown(window, { key: 'Enter', ctrlKey: true })
    expect(active).toHaveBeenCalledTimes(1)
    expect(hidden).not.toHaveBeenCalled()
    fireEvent.keyDown(window, { key: 'Enter', ctrlKey: true, repeat: true })
    expect(active).toHaveBeenCalledTimes(1)
  })
  it('requires the same confirmation for a negative verdict with the hotkey', () => {
    const submit = vi.fn()
    render(
      <ReviewFeedbackForm
        verdicts={ternaryVerdictScale}
        onSubmit={submit}
        initialDraft={{ verdictValue: 'rejected', comment: '', reactionId: null }}
      />,
    )
    fireEvent.keyDown(window, { key: 'Enter', metaKey: true })
    expect(submit).not.toHaveBeenCalled()
    expect(screen.getByText('Незачёт без комментария. Отправить всё равно?')).toBeTruthy()
    fireEvent.keyDown(window, { key: 'Enter', metaKey: true })
    expect(submit).toHaveBeenCalledTimes(1)
  })
})
