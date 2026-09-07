import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { staffStatisticsResponseSchema } from '@vmsh/contracts'
import { LessonStatistics } from './lesson-statistics'

afterEach(cleanup)

export const liveStatistics = staffStatisticsResponseSchema.parse({
  schemaVersion: 1,
  courses: [],
  selectedCourseId: null,
  selectedGroupId: null,
  run: null,
  lessons: [],
  requestId: 'test',
  lessonNumbers: [0, 1],
  basicLesson: {
    lessonNumber: 0,
    groups: [
      {
        groupId: 'g-1',
        code: 'н',
        name: 'Начинающие',
        participantCount: 1,
        distribution: [0.5],
        problems: [
          {
            problemId: 'p-1',
            label: '0н.1',
            title: 'Точки',
            points: 0.5,
            tried: 1,
            share: 50,
            difficultyWeak: null,
            difficultyStrong: null,
          },
        ],
      },
    ],
  },
  students: [{ studentId: 'u-1', name: 'Тестовый Ученик' }],
  personal: [],
})

it('shows fractional live points and a singleton without a model run', () => {
  const lesson = vi.fn(),
    student = vi.fn(),
    refresh = vi.fn()
  render(
    <LessonStatistics
      data={liveStatistics}
      onLessonChange={lesson}
      studentId={null}
      onStudentChange={student}
      onRefresh={refresh}
    />,
  )
  expect(screen.getByText('0,5')).toBeTruthy()
  expect(screen.getByText('50.0%')).toBeTruthy()
  expect(screen.getAllByText('Ещё не рассчитано')).toHaveLength(2)
  expect(screen.getByRole('img', { name: /один участник/ })).toBeTruthy()
  fireEvent.change(screen.getByLabelText('Занятие'), { target: { value: '1' } })
  expect(lesson).toHaveBeenCalledWith(1)
  fireEvent.change(screen.getByLabelText('График школьника'), { target: { value: 'Тестовый' } })
  fireEvent.click(screen.getByRole('button', { name: 'Тестовый Ученик' }))
  expect(student).toHaveBeenCalledWith('u-1')
  fireEvent.click(screen.getByRole('button', { name: 'Обновить статистику' }))
  expect(refresh).toHaveBeenCalledOnce()
})

it('shows empty submissions and an empty personal model', () => {
  const data = {
    ...liveStatistics,
    basicLesson: {
      ...liveStatistics.basicLesson!,
      groups: liveStatistics.basicLesson!.groups.map((g) => ({
        ...g,
        participantCount: 0,
        distribution: [],
      })),
    },
  }
  render(
    <LessonStatistics
      data={data}
      onLessonChange={() => {}}
      studentId="u-1"
      onStudentChange={() => {}}
      onRefresh={() => {}}
    />,
  )
  expect(screen.getByText(/пока нет отправок/)).toBeTruthy()
  expect(screen.getByText(/пока нет расчёта силы/)).toBeTruthy()
})
