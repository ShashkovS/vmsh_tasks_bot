import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import assignmentFixture from '@vmsh/contracts/fixtures/classrooms/assignment-plan.v1.json'
import { classroomAssignmentPlanResponseSchema } from '@vmsh/contracts'

import { ClassroomAssignmentStats } from './classroom-event-page'

afterEach(() => cleanup())

describe('classroom event assignment statistics', () => {
  it('shows every room, its selected level and current student count', () => {
    const base = classroomAssignmentPlanResponseSchema.parse(assignmentFixture).assignmentPlan
    const room = base.rooms[0]!
    const student = base.students[0]!
    const plan = {
      ...base,
      rooms: [
        room,
        {
          ...room,
          publicId: 'room-202',
          name: '202',
        },
      ],
      students: [
        student,
        {
          ...student,
          enrollmentPublicId: 'enrollment-boris',
          studentPublicId: 'student-boris',
          surname: 'Иванов',
          name: 'Борис',
        },
      ],
    }

    render(<ClassroomAssignmentStats plan={plan} />)

    const room201 = screen.getByRole('row', { name: /201/ })
    expect(within(room201).getByText('н · Начинающие')).toBeTruthy()
    expect(within(room201).getByText('2')).toBeTruthy()
    const room202 = screen.getByRole('row', { name: /202/ })
    expect(within(room202).getByText('н · Начинающие')).toBeTruthy()
    expect(within(room202).getByText('0')).toBeTruthy()
  })
})
