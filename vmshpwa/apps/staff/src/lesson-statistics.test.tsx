import { cleanup, fireEvent, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { staffStatisticsResponseSchema, type StaffStatisticsResponse } from '@vmsh/contracts'
import { renderWithI18n as render } from '@vmsh/test-utils/i18n'
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
  expect(screen.getByRole('columnheader', { name: 'Решили' })).toBeTruthy()
  expect(screen.queryByText('Баллы')).toBeNull()
  expect(screen.getByRole('img', { name: /Число решённых задач/i }).getAttribute('viewBox')).toBe(
    '0 0 220 260',
  )
  expect(screen.getByText('50.0%')).toBeTruthy()
  expect(screen.getAllByText('Ещё не рассчитано')).toHaveLength(2)
  expect(screen.getByRole('img', { name: /один участник/ })).toBeTruthy()
  const point = screen.getByRole('img', { name: /один участник/ }).querySelector('circle')!
  expect(point.getAttribute('class')).toBe('fill-chart-2')
  expect(Number(point.getAttribute('cy'))).toBe(130)
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

// docs/lesson-statistics.md#staff-violin-polish-2026-10-05: colours survive filters/order.
it.each([false, true])(
  'keeps group colours for singleton=%s when reordered or filtered',
  (singleton) => {
    const groups = [
      ['н', 'Начинающие', '2'],
      ['п', 'Продолжающие', '3'],
      ['э', 'Эксперты', '5'],
    ].map(([code, name, color]) => ({
      ...liveStatistics.basicLesson!.groups[0]!,
      groupId: `g-${code}`,
      code: code!,
      name: name!,
      color: color!,
      participantCount: singleton ? 1 : 3,
      distribution: singleton ? [0.5] : [0, 0.5, 1],
    }))
    const view = (selected: typeof groups) => {
      const data: StaffStatisticsResponse = {
        ...liveStatistics,
        basicLesson: { ...liveStatistics.basicLesson!, groups: selected },
      }
      return (
        <LessonStatistics
          data={data}
          onLessonChange={() => {}}
          studentId={null}
          onStudentChange={() => {}}
          onRefresh={() => {}}
        />
      )
    }
    const { rerender } = render(view(groups))
    for (const selected of [groups, [...groups].reverse(), [groups[2]!]]) {
      rerender(view(selected))
      for (const group of selected) {
        const figure = screen
          .getByText(
            `${group.name} · ${group.participantCount} ${singleton ? 'участник' : 'участников'}`,
          )
          .closest('figure')!
        expect(
          figure.querySelector(singleton ? 'circle' : 'path')!.getAttribute('class'),
        ).toContain(`fill-chart-${group.color}`)
        if (!singleton) {
          expect([...figure.querySelectorAll('svg text')].map((tick) => tick.textContent)).toEqual([
            '0',
            '1',
          ])
        }
      }
    }
  },
)
