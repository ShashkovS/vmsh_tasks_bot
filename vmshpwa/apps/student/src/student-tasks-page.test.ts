import { describe, expect, it } from 'vitest'

import studentAccessFixture from '../../../packages/contracts/fixtures/courses/student-access.v1.json'
import studentLessonsFixture from '../../../packages/contracts/fixtures/courses/student-lessons.v1.json'
import { studentCourseAccessResponseSchema, studentLessonListResponseSchema } from '@vmsh/contracts'

import {
  lessonHeading,
  publishedMaterialLabel,
  resolveStudentTasksContext,
  studentTasksSearchSchema,
} from './student-tasks-view'

const access = studentCourseAccessResponseSchema.parse(studentAccessFixture.response)
const lessons = studentLessonListResponseSchema.parse(studentLessonsFixture.response).lessons

describe('Student production Tasks mapping', () => {
  it('uses the first course and its active group when URL context is omitted', () => {
    expect(resolveStudentTasksContext(access, studentTasksSearchSchema.parse({}))).toMatchObject({
      kind: 'ready',
      enrollment: { enrollmentId: 'enrollment-fixture-alpha' },
      groupId: 'group-fixture-alpha-one',
    })
  })

  it('allows another granted group but rejects a foreign course or group', () => {
    expect(
      resolveStudentTasksContext(
        access,
        studentTasksSearchSchema.parse({
          course: 'course-fixture-alpha',
          group: 'group-fixture-alpha-two',
        }),
      ),
    ).toMatchObject({ kind: 'ready', groupId: 'group-fixture-alpha-two' })
    expect(
      resolveStudentTasksContext(
        access,
        studentTasksSearchSchema.parse({ course: 'course-not-granted' }),
      ),
    ).toEqual({ kind: 'forbidden', resource: 'course' })
    expect(
      resolveStudentTasksContext(
        access,
        studentTasksSearchSchema.parse({
          course: 'course-fixture-alpha',
          group: 'group-not-granted',
        }),
      ),
    ).toEqual({ kind: 'forbidden', resource: 'group' })
  })

  it('uses only actual publication state in archive labels', () => {
    expect(lessonHeading(lessons[0]!)).toBe('Занятие 42')
    expect(publishedMaterialLabel(lessons[0]!)).toBe('Только условие')
    expect(publishedMaterialLabel(lessons[1]!)).toBe('Есть подсказка и решение')
  })

  it('rejects malformed shareable context before the page uses it', () => {
    expect(studentTasksSearchSchema.safeParse({ course: '../staff' }).success).toBe(false)
    expect(studentTasksSearchSchema.safeParse({ lesson: 0 }).success).toBe(false)
    expect(studentTasksSearchSchema.parse({ view: 'sheet', topic: 'геометрия' })).toMatchObject({
      view: 'sheet',
      topic: 'геометрия',
    })
  })
})
