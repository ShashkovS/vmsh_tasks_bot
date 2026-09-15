import { describe, expect, it } from 'vitest'

import studentAccessFixture from '../../../packages/contracts/fixtures/courses/student-access.v1.json'
import studentLessonsFixture from '../../../packages/contracts/fixtures/courses/student-lessons.v1.json'
import studentProblemsFixture from '../../../packages/contracts/fixtures/courses/student-problems.v1.json'
import {
  studentCourseAccessResponseSchema,
  studentLessonListResponseSchema,
  studentProblemListResponseSchema,
} from '@vmsh/contracts'

import {
  lessonHeading,
  publishedMaterialLabel,
  resolveStudentTasksContext,
  studentTasksSearchSchema,
  toStudentTaskView,
} from './student-tasks-view'

const access = studentCourseAccessResponseSchema.parse(studentAccessFixture.response)
const lessons = studentLessonListResponseSchema.parse(studentLessonsFixture.response).lessons
const problems = studentProblemListResponseSchema.parse(studentProblemsFixture.response).problems

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

  it('rejects malformed shareable context and accepts the real zero lesson', () => {
    expect(studentTasksSearchSchema.safeParse({ course: '../staff' }).success).toBe(false)
    expect(studentTasksSearchSchema.safeParse({ lesson: 0 }).success).toBe(true)
    expect(studentTasksSearchSchema.parse({ view: 'sheet', topic: 'геометрия' })).toMatchObject({
      view: 'sheet',
      topic: 'геометрия',
    })
  })

  it('maps real server states and opaque identities into Product task rows', () => {
    expect(problems.map((problem) => toStudentTaskView(problem, 42, 'н'))).toEqual([
      expect.objectContaining({
        id: 'p-42-1',
        number: '42н.1',
        status: { kind: 'accepted', label: 'Зачтено', tone: 'success' },
        verdict: expect.objectContaining({ value: 'plus', symbol: '✅+', weight: 1 }),
      }),
      expect.objectContaining({
        id: 'p-42-2',
        status: { kind: 'checking', label: 'На проверке', tone: 'info' },
      }),
      expect.objectContaining({
        id: 'p-42-3',
        number: '42н.3а',
        status: { kind: 'needs-work', label: 'Нужна доработка', tone: 'warning' },
        verdict: expect.objectContaining({ value: 'plus-minus', symbol: '🟨±', weight: 0.7 }),
      }),
    ])
  })
})
