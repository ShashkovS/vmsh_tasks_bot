import { describe, expect, it } from 'vitest'

import studentHomeFixture from '../../../packages/contracts/fixtures/courses/student-home.v1.json'
import { studentHomeContractFixtureSchema } from '@vmsh/contracts'

import { studentPhaseLabel, toCourseEnrollmentView } from './student-home-view'

const response = studentHomeContractFixtureSchema.parse(studentHomeFixture).response

describe('Student production home mapping', () => {
  it('maps server course/group identity without introducing status colors', () => {
    const course = response.courses[0]
    if (!course) throw new Error('Expected a fixture course')

    expect(toCourseEnrollmentView(course)).toMatchObject({
      course: {
        id: 'course-fixture-alpha',
        accentIndex: 1,
      },
      activeGroupId: 'group-fixture-alpha-one',
      attendanceMode: 'in-person',
      allowedGroups: [
        { id: 'group-fixture-alpha-one', colorIndex: 1 },
        { id: 'group-fixture-alpha-two', colorIndex: 2 },
      ],
    })
  })

  it('uses the independent server phase and absolute cutoff in the lesson timezone', () => {
    const course = response.courses[0]
    if (!course) throw new Error('Expected a fixture course')

    expect(studentPhaseLabel(course)).toContain('Решаем задачи')
    expect(studentPhaseLabel(course)).toContain('26 сентября')
  })

  it('does not invent a date or progress when a course has no published lesson', () => {
    const course = response.courses[1]
    if (!course) throw new Error('Expected an empty fixture course')

    expect(studentPhaseLabel(course)).toBe('Новое занятие пока не опубликовано')
  })
})
