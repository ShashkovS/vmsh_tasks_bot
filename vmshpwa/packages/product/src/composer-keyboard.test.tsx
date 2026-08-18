import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { SubmissionComposer } from './submission-composer'
import { SupportComposer } from './support-dialogue'

afterEach(() => cleanup())

describe('composer keyboard submission', () => {
  it('sends a support message with Ctrl+Enter and Cmd+Enter', () => {
    const onSubmit = vi.fn()
    render(<SupportComposer onSubmit={onSubmit} onValueChange={() => undefined} value="Вопрос" />)

    const message = screen.getByLabelText('Сообщение')
    fireEvent.keyDown(message, { key: 'Enter', ctrlKey: true })
    fireEvent.keyDown(message, { key: 'Enter', metaKey: true })

    expect(onSubmit).toHaveBeenCalledTimes(2)
  })

  it('sends a written solution with Ctrl+Enter', () => {
    const onSubmit = vi.fn()
    render(
      <SubmissionComposer
        attachments={[]}
        onSubmit={onSubmit}
        onTextChange={() => undefined}
        taskType="written"
        text="Решение"
      />,
    )

    fireEvent.keyDown(screen.getByLabelText('Ваше решение'), { key: 'Enter', ctrlKey: true })

    expect(onSubmit).toHaveBeenCalledOnce()
  })

  it('reports only the pasted character count', () => {
    const onTextPaste = vi.fn()
    render(
      <SubmissionComposer
        attachments={[]}
        onTextChange={() => undefined}
        onTextPaste={onTextPaste}
        taskType="written"
        text=""
      />,
    )

    fireEvent.paste(screen.getByLabelText('Ваше решение'), {
      clipboardData: { getData: () => 'Скопированный текст' },
    })

    expect(onTextPaste).toHaveBeenCalledOnce()
    expect(onTextPaste).toHaveBeenCalledWith('Скопированный текст'.length)
  })
})
