import type { Meta, StoryObj } from '@storybook/react-vite'
import { staffStatisticsResponseSchema } from '@vmsh/contracts'
import { LessonStatistics } from './lesson-statistics'

const meta = { title: 'Staff/Lesson statistics', component: LessonStatistics } satisfies Meta<
  typeof LessonStatistics
>
export default meta
type Story = StoryObj<typeof meta>
export const LiveWithoutModel: Story = {
  args: {
    data: staffStatisticsResponseSchema.parse({
      schemaVersion: 1,
      courses: [],
      selectedCourseId: null,
      selectedGroupId: null,
      run: null,
      lessons: [],
      requestId: 'story',
      lessonNumbers: [0],
      basicLesson: {
        lessonNumber: 0,
        groups: [
          {
            groupId: 'g-1',
            code: 'н',
            name: 'Начинающие',
            participantCount: 4,
            distribution: [0, 0.5, 1, 1],
            problems: [
              {
                problemId: 'p-1',
                label: '0н.1',
                title: 'Точки',
                points: 2.5,
                tried: 4,
                share: 62.5,
                difficultyWeak: null,
                difficultyStrong: null,
              },
            ],
          },
        ],
      },
      students: [],
      personal: [],
    }),
    studentId: null,
    onStudentChange: () => {},
    onLessonChange: () => {},
    onRefresh: () => {},
  },
}
