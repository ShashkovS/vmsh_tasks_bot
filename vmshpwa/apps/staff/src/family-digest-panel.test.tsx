import { i18n } from '@lingui/core'
import { cleanup, screen } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'

import { renderWithI18n as render } from '@vmsh/test-utils/i18n'

import { FamilyDigestPanelView } from './family-digest-panel'

afterEach(cleanup)

it('localizes the digest interface while preserving group and student data', () => {
  i18n.activate('en')
  render(
    <FamilyDigestPanelView
      digest={{
        groupLessonId: 'lesson.math.41',
        courseId: 'course.math',
        courseName: 'Математика 5–7',
        groupId: 'group.beginner',
        groupName: 'Начинающие',
        lessonNumber: 41,
        studentCount: 2,
        familyCount: 1,
        alreadySentFamilyCount: 0,
        pendingFamilyCount: 1,
        unlinkedStudents: [{ studentId: 'student-1', displayName: 'Петрова Анна' }],
      }}
      onStart={() => undefined}
    />,
  )

  expect(screen.getByText('Family summary')).toBeTruthy()
  expect(screen.getByText('Group')).toBeTruthy()
  expect(screen.getByText('Начинающие')).toBeTruthy()
  expect(screen.getByText('Петрова Анна')).toBeTruthy()
})
