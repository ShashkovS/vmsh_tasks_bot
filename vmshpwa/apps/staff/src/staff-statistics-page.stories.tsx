import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import { staffStatisticsResponseSchema, type StaffStatisticsResponse } from '@vmsh/contracts'

import { StaffStatisticsView } from './staff-statistics-page'

const courses = [
  {
    courseId: 'course.math-5-7',
    code: 'math-5-7',
    name: 'Математика 5–7',
    subjectCode: 'math',
    status: 'active',
    groups: [
      {
        groupId: 'group.beginner',
        code: 'н',
        name: 'Начинающие',
        colorKey: 'beginner',
        status: 'active',
      },
      {
        groupId: 'group.continuing',
        code: 'п',
        name: 'Продолжающие',
        colorKey: 'continuing',
        status: 'active',
      },
    ],
  },
  {
    courseId: 'course.physics-7',
    code: 'physics-7',
    name: 'Физика 7',
    subjectCode: 'physics',
    status: 'active',
    groups: [
      {
        groupId: 'group.physics-main',
        code: 'ф7',
        name: 'Основная группа',
        colorKey: 'neutral',
        status: 'active',
      },
    ],
  },
] as const

function statisticsFixture(groupId: string | null): StaffStatisticsResponse {
  const selectedGroup =
    groupId === null
      ? [
          {
            groupId: 'group.beginner',
            code: 'н',
            name: 'Начинающие',
            colorKey: 'beginner',
            sortOrder: 1,
            studentCount: 4,
          },
          {
            groupId: 'group.continuing',
            code: 'п',
            name: 'Продолжающие',
            colorKey: 'continuing',
            sortOrder: 2,
            studentCount: 3,
          },
        ]
      : [
          {
            groupId,
            code: groupId === 'group.beginner' ? 'н' : 'п',
            name: groupId === 'group.beginner' ? 'Начинающие' : 'Продолжающие',
            colorKey: groupId === 'group.beginner' ? 'beginner' : 'continuing',
            sortOrder: groupId === 'group.beginner' ? 1 : 2,
            studentCount: groupId === 'group.beginner' ? 4 : 3,
          },
        ]
  const values =
    groupId === 'group.continuing'
      ? [3, 4, 5]
      : groupId === 'group.beginner'
        ? [1, 2, 3, 5]
        : [1, 2, 3, 3, 4, 5, 6]
  const studentCount = values.length
  return staffStatisticsResponseSchema.parse({
    schemaVersion: 1,
    courses,
    selectedCourseId: 'course.math-5-7',
    selectedGroupId: groupId,
    run: {
      runId: 'analytics.run-2026-08-02',
      algorithm: 'a53-compatible',
      algorithmVersion: '1',
      inputThroughResultId: 18791,
      completedAt: '2026-08-02T12:15:00Z',
    },
    lessons: [
      {
        lessonNumber: 40,
        studentCount,
        meanSimpleStrength: 6.4,
        meanComplexStrength: 3.7,
        meanMaxComplexStrength: 7.9,
        meanSolvedItems: 2.7,
        completionRate: 54.3,
        solvedDistribution: values.map((value) => Math.max(0, value - 1)),
        groups: selectedGroup,
      },
      {
        lessonNumber: 41,
        studentCount,
        meanSimpleStrength: 6.9,
        meanComplexStrength: 4.2,
        meanMaxComplexStrength: 8.1,
        meanSolvedItems: 3.4,
        completionRate: 68.6,
        solvedDistribution: values,
        groups: selectedGroup,
      },
    ],
    requestId: 'story-staff-statistics',
  })
}

function HistoricalHarness() {
  const [groupId, setGroupId] = useState<string | null>(null)
  const [lessonNumber, setLessonNumber] = useState<number | null>(null)
  return (
    <StaffStatisticsView
      data={statisticsFixture(groupId)}
      lessonNumber={lessonNumber}
      onCourseChange={() => undefined}
      onGroupChange={setGroupId}
      onLessonChange={setLessonNumber}
    />
  )
}

const empty = staffStatisticsResponseSchema.parse({
  schemaVersion: 1,
  courses,
  selectedCourseId: 'course.math-5-7',
  selectedGroupId: null,
  run: null,
  lessons: [],
  requestId: 'story-staff-statistics-empty',
})

const meta = {
  title: 'Pages/Staff/Statistics',
  component: StaffStatisticsView,
  parameters: { layout: 'fullscreen' },
} satisfies Meta<typeof StaffStatisticsView>

export default meta
type Story = StoryObj<typeof meta>

export const HistoricalCourse: Story = {
  name: 'История курса и анонимное распределение',
  args: {
    data: statisticsFixture(null),
    lessonNumber: null,
    onCourseChange: () => undefined,
    onGroupChange: () => undefined,
    onLessonChange: () => undefined,
  },
  render: () => <HistoricalHarness />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByRole('heading', { name: 'Статистика курса' })).toBeInTheDocument()
    await expect(canvas.getByRole('img', { name: /Распределение по группе/ })).toBeInTheDocument()
    await expect(canvas.queryByText(/место школьника|процентиль ученика/i)).not.toBeInTheDocument()

    await userEvent.click(canvas.getByRole('button', { name: 'Занятие 40' }))
    await expect(canvas.getByRole('heading', { name: 'Занятие 40' })).toBeInTheDocument()

    await userEvent.selectOptions(canvas.getByLabelText('Группа'), 'group.continuing')
    await expect(canvas.getByLabelText('Группа')).toHaveValue('group.continuing')
    await expect(canvas.getByText('Состав агрегата')).toBeInTheDocument()
  },
}

export const NoCompletedRun: Story = {
  name: 'Расчётов пока нет',
  args: {
    data: empty,
    lessonNumber: null,
    onCourseChange: () => undefined,
    onGroupChange: () => undefined,
    onLessonChange: () => undefined,
  },
}
