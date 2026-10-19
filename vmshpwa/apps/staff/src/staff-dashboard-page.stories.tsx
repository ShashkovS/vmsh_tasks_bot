import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, within } from 'storybook/test'

import { staffDashboardResponseSchema } from '@vmsh/contracts'

import { StaffDashboardView } from './staff-dashboard-page'

const currentWeek = staffDashboardResponseSchema.parse({
  schemaVersion: 1,
  generatedAt: '2026-08-02T12:00:00Z',
  summary: {
    review: { totalCases: 27, claimedByOthers: 4 },
    questions: { awaitingStaff: 5, olderThanOneHour: 2 },
    publications: { conditionsPublished: 2, groupLessons: 3 },
    oral: { openWindows: 1, upcomingWindows: 1 },
    delivery: { failedBatches: 1, failedRecipients: 3 },
  },
  lessons: [
    {
      groupLessonId: 'lesson.math.beginner.41',
      lessonNumber: 41,
      cycleAnchorDate: '2026-08-02',
      course: { courseId: 'course.math', code: 'math', name: 'Математика 5–7' },
      group: { groupId: 'group.beginner', code: 'н', name: 'Начинающие', colorKey: 'beginner' },
      phase: 'active',
      publications: {
        condition: { state: 'published', scheduledAt: null },
        hint: { state: 'scheduled', scheduledAt: '2026-08-08T15:00:00Z' },
        solution: { state: 'none', scheduledAt: null },
      },
      oral: { openWindows: 1, upcomingWindows: 0 },
    },
    {
      groupLessonId: 'lesson.math.continuing.41',
      lessonNumber: 41,
      cycleAnchorDate: '2026-08-02',
      course: { courseId: 'course.math', code: 'math', name: 'Математика 5–7' },
      group: {
        groupId: 'group.continuing',
        code: 'п',
        name: 'Продолжающие',
        colorKey: 'continuing',
      },
      phase: 'hints_published',
      publications: {
        condition: { state: 'published', scheduledAt: null },
        hint: { state: 'published', scheduledAt: null },
        solution: { state: 'scheduled', scheduledAt: '2026-08-08T18:00:00Z' },
      },
      oral: { openWindows: 0, upcomingWindows: 1 },
    },
    {
      groupLessonId: 'lesson.physics.main.7',
      lessonNumber: 7,
      cycleAnchorDate: '2026-08-04',
      course: { courseId: 'course.physics', code: 'physics', name: 'Физика 7' },
      group: { groupId: 'group.physics', code: 'ф7', name: 'Основная', colorKey: 'neutral' },
      phase: 'draft',
      publications: {
        condition: { state: 'none', scheduledAt: null },
        hint: { state: 'none', scheduledAt: null },
        solution: { state: 'none', scheduledAt: null },
      },
      oral: { openWindows: 0, upcomingWindows: 0 },
    },
  ],
  requestId: 'story-dashboard',
})

const meta = {
  title: 'Pages/Staff/Dashboard',
  component: StaffDashboardView,
  parameters: { layout: 'fullscreen' },
} satisfies Meta<typeof StaffDashboardView>

export default meta
type Story = StoryObj<typeof meta>

export const CurrentWeek: Story = {
  name: 'Текущая неделя администратора',
  args: { data: currentWeek },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByRole('heading', { name: 'Рабочая сводка' })).toBeInTheDocument()
    await expect(canvas.getByText('27')).toBeInTheDocument()
    await expect(canvas.getAllByText('По расписанию')).toHaveLength(2)
  },
}

export const TeacherScoped: Story = {
  name: 'Только доступные группы учителя',
  args: {
    data: staffDashboardResponseSchema.parse({
      ...currentWeek,
      summary: {
        ...currentWeek.summary,
        publications: { conditionsPublished: 1, groupLessons: 1 },
        delivery: null,
      },
      lessons: currentWeek.lessons.slice(0, 1),
      requestId: 'story-dashboard-teacher',
    }),
  },
}

export const NoCurrentLessons: Story = {
  name: 'Нет текущих занятий',
  args: {
    data: staffDashboardResponseSchema.parse({
      ...currentWeek,
      summary: {
        review: { totalCases: 0, claimedByOthers: 0 },
        questions: { awaitingStaff: 0, olderThanOneHour: 0 },
        publications: { conditionsPublished: 0, groupLessons: 0 },
        oral: { openWindows: 0, upcomingWindows: 0 },
        delivery: null,
      },
      lessons: [],
      requestId: 'story-dashboard-empty',
    }),
  },
}
