import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { courseEnrollmentSchema } from '@vmsh/contracts'
import studentAccessFixture from '@vmsh/contracts/fixtures/courses/student-access.v1.json'

import { StudentEnrollmentSettings } from './student-profile-page'

afterEach(() => cleanup())

describe('Student course settings', () => {
  it('requires confirmation before changing group and attendance', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined)
    const enrollment = courseEnrollmentSchema.parse(studentAccessFixture.response.enrollments[0])
    render(
      <StudentEnrollmentSettings
        enrollment={enrollment}
        error={false}
        saving={false}
        onSave={onSave}
      />,
    )

    fireEvent.change(screen.getByLabelText('Активная группа'), {
      target: { value: enrollment.allowedGroups[1]!.groupId },
    })
    fireEvent.change(screen.getByLabelText('Формат занятий'), {
      target: { value: 'in_person' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Изменить' }))
    expect(onSave).not.toHaveBeenCalled()
    expect(screen.getByText(/для вас резервируют место/)).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Подтвердить изменения' }))
    await waitFor(() =>
      expect(onSave).toHaveBeenCalledWith({
        activeGroupId: enrollment.allowedGroups[1]!.groupId,
        attendanceMode: 'in_person',
        version: enrollment.version,
      }),
    )
  })
})
