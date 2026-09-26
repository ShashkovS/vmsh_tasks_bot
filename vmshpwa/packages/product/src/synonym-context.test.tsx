import { i18n } from '@lingui/core'
import { cleanup, screen } from '@testing-library/react'
import { renderWithI18n } from '@vmsh/test-utils/i18n'
import { afterEach, expect, it } from 'vitest'
import { SynonymMergeSplitPreview } from './synonym-context'

afterEach(cleanup)

// P6: Russian plural categories cannot select English singular at 21.
it.each([0, 1, 2, 5, 11, 21])(
  'renders English counts for %i while preserving problem data',
  (count) => {
    i18n.activate('en')
    renderWithI18n(
      <SynonymMergeSplitPreview
        mode="merge"
        problems={[
          {
            problemId: 'problem-1',
            courseName: 'Курс',
            groupName: 'Группа',
            lessonNumber: 2,
            taskNumber: '1а',
            title: 'Авторская задача',
            taskType: 'Written',
            submissionCount: count,
            reviewCount: count,
          },
        ]}
      />,
    )
    expect(
      screen.getByText(`${count} ${count === 1 ? 'submission' : 'submissions'}`, { exact: true }),
    ).toBeTruthy()
    expect(screen.getByText('1а · Авторская задача')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Merge' })).toBeTruthy()
  },
)
