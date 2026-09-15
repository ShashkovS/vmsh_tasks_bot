import { describe, expect, it } from 'vitest'

import studentAccessFixture from '../../../packages/contracts/fixtures/courses/student-access.v1.json'
import { studentCourseAccessResponseSchema } from '@vmsh/contracts'

import { resolveStudentTasksContext, studentTasksSearchSchema } from './student-tasks-view'

const access = studentCourseAccessResponseSchema.parse(studentAccessFixture.response)

describe('Student task-list URL context', () => {
  it('uses readable course and group codes while accepting old opaque links', () => {
    expect(
      resolveStudentTasksContext(
        access,
        studentTasksSearchSchema.parse({ course: 'synthetic-alpha', group: 'alpha-two' }),
      ),
    ).toMatchObject({
      kind: 'ready',
      enrollment: { enrollmentId: 'enrollment-fixture-alpha' },
      groupId: 'group-fixture-alpha-two',
    })
    expect(
      resolveStudentTasksContext(
        access,
        studentTasksSearchSchema.parse({
          course: 'course-fixture-alpha',
          group: 'group-fixture-alpha-two',
        }),
      ),
    ).toMatchObject({ kind: 'ready', groupId: 'group-fixture-alpha-two' })
  })

  it('allows a short Cyrillic group code but rejects a path fragment', () => {
    expect(studentTasksSearchSchema.parse({ course: 'vmsh', group: 'н' })).toMatchObject({
      course: 'vmsh',
      group: 'н',
    })
    expect(studentTasksSearchSchema.safeParse({ course: '../staff' }).success).toBe(false)
  })
})
