import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, within } from 'storybook/test'
import { CourseSummary } from './staff-statistics-reports'

const meta = {
  title: 'Pages/Staff/Course summary',
  component: CourseSummary,
  parameters: { layout: 'fullscreen' },
  decorators: [
    (Story) => (
      <div className="staff-statistics p-4">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof CourseSummary>
export default meta
type Story = StoryObj<typeof meta>
export const ReviewWorkload: Story = {
  args: {
    data: {
      schemaVersion: 1,
      courses: [],
      selectedCourseId: null,
      selectedGroupId: null,
      requestId: 'story',
      lessons: [
        {
          lessonNumber: 0,
          students: 700,
          allPlus: 1500.5,
          botPlus: 1000,
          writtenPlus: 200.5,
          writtenWrittenPlus: 100,
          writtenOralPlus: 100.5,
          zoomPlus: 200,
          schoolPlus: 100,
          writtenChecked: 800,
          writtenPending: 30,
          writtenTotal: 830,
          writtenStudents: 200,
          zoomStudents: 100,
          schoolStudents: 50,
        },
      ],
    },
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(
      canvas.getByRole('columnheader', { name: 'Всего с учётом ожидающих' }),
    ).toBeInTheDocument()
    await expect(canvas.getByRole('cell', { name: '830' })).toBeInTheDocument()
  },
}
