import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { StudentSubmissionDeadlineNotice } from './student-submission-deadline-notice'

afterEach(() => cleanup())

describe('submission deadline notice', () => {
  it('explains the closed window without exposing service diagnostics', () => {
    render(<StudentSubmissionDeadlineNotice />)

    const notice = screen.getByRole('status')
    expect(notice.textContent).toContain('Приём завершён')
    expect(notice.textContent).toContain(
      'Срок сдачи закончился, поэтому ответ не отправлен. Черновик сохранён на этом устройстве.',
    )
    expect(notice.textContent).not.toMatch(/api:|409|request=/i)
    expect(screen.queryByRole('button')).toBeNull()
  })
})
