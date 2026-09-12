import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { CourseEnrollment } from '@vmsh/contracts'

import { FamilyEnrollmentSettings } from './family-children-page'

const enrollment: CourseEnrollment = {
  enrollmentId: 'enrollment.family-test',
  studentId: 'student.family-test',
  course: {
    courseId: 'course.math',
    code: 'math',
    name: 'Математика',
    subjectCode: 'math',
    status: 'active',
    sortOrder: 1,
    accentKey: 'math',
    version: 1,
  },
  activeGroupId: 'group.beginner',
  allowedGroups: [
    {
      groupId: 'group.beginner',
      courseId: 'course.math',
      code: 'beginner',
      name: 'Начинающие',
      status: 'active',
      sortOrder: 1,
      colorKey: 'level-1',
      version: 1,
    },
    {
      groupId: 'group.continuing',
      courseId: 'course.math',
      code: 'continuing',
      name: 'Продолжающие',
      status: 'active',
      sortOrder: 2,
      colorKey: 'level-2',
      version: 1,
    },
  ],
  attendanceMode: 'online',
  status: 'active',
  version: 4,
}

afterEach(() => cleanup())

describe('Family course enrollment settings', () => {
  it('reviews the resource consequence before saving the selected values', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined)
    render(
      <FamilyEnrollmentSettings
        enrollment={enrollment}
        error={false}
        saving={false}
        onSave={onSave}
      />,
    )

    fireEvent.change(screen.getByLabelText('Группа'), {
      target: { value: 'group.continuing' },
    })
    fireEvent.change(screen.getByLabelText('Формат занятий'), {
      target: { value: 'in_person' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Изменить' }))

    expect(onSave).not.toHaveBeenCalled()
    expect(screen.getByText(/организаторы резервируют место/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Подтвердить изменения' }))

    await waitFor(() =>
      expect(onSave).toHaveBeenCalledWith({
        activeGroupId: 'group.continuing',
        attendanceMode: 'in_person',
        version: 4,
      }),
    )
  })
})
