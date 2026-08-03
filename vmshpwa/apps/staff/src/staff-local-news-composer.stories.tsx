import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, fn, userEvent, within } from 'storybook/test'

import type { AdminCourse } from '@vmsh/contracts'

import { StaffLocalNewsComposer } from './staff-local-news-composer'

const courses: AdminCourse[] = [
  {
    courseId: 'course.math',
    code: 'math',
    name: 'Математика 5–7',
    subjectCode: 'math',
    status: 'active',
    sortOrder: 10,
    accentKey: 'math',
    activeStudents: 120,
    version: 1,
    groups: [
      {
        groupId: 'group.beginners',
        shortCode: 'n',
        name: 'Начинающие',
        status: 'active',
        colorKey: 'level-1',
        sortOrder: 10,
        allowSelfSwitch: true,
        isDefault: true,
        isSystem: false,
        scoreWeight: 1,
        activeStudents: 48,
        version: 1,
      },
    ],
  },
]

const meta = {
  title: 'Pages/Staff/Local news composer',
  component: StaffLocalNewsComposer,
  args: {
    courses,
    draft: {
      owner: 'group:group.beginners',
      text: 'Разбор задач состоится завтра в 17:00.',
      publishedLocal: '2026-08-04T17:00',
    },
    onChange: fn(),
    onSubmit: fn(),
  },
  decorators: [
    (Story) => (
      <div className="max-w-xl rounded-lg border border-border bg-surface p-5">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof StaffLocalNewsComposer>

export default meta
type Story = StoryObj<typeof meta>

export const Scheduled: Story = {
  play: async ({ canvasElement, args }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByDisplayValue('Начинающие')).toBeInTheDocument()
    await expect(canvas.getByDisplayValue(/Разбор задач/)).toBeInTheDocument()
    await userEvent.click(canvas.getByRole('button', { name: 'Запланировать публикацию' }))
    await expect(args.onSubmit).toHaveBeenCalledOnce()
  },
}
