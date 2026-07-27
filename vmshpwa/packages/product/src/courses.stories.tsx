import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import { CourseCard, CourseGroupSwitcher } from './course-context'
import { mathCourse, mathGroups, physicsCourse, physicsGroups } from './course-fixtures'
import type { CourseEnrollmentView } from './types'

const meta = {
  title: 'Product/Courses',
  parameters: { layout: 'padded' },
} satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

const mathEnrollment: CourseEnrollmentView = {
  course: mathCourse,
  activeGroupId: 'math-continuing',
  allowedGroups: mathGroups,
  attendanceMode: 'in-person',
}

const physicsEnrollment: CourseEnrollmentView = {
  course: physicsCourse,
  activeGroupId: 'physics-lab',
  allowedGroups: physicsGroups,
  attendanceMode: 'online',
}

export const StudentMultipleCourses: Story = {
  name: 'Student multiple courses',
  render: () => (
    <div className="mx-auto max-w-3xl space-y-3">
      <CourseCard
        classroomName="301"
        enrollment={mathEnrollment}
        lessonDate="26 января"
        lessonNumber={41}
        phase="Решения откроются в воскресенье"
        progressLabel="3 задачи зачтено · 2 ждут проверки"
      />
      <CourseCard
        enrollment={physicsEnrollment}
        lessonDate="29 января"
        lessonNumber={7}
        phase="Условие опубликовано сегодня"
        progressLabel="1 опыт описан · есть черновик"
      />
    </div>
  ),
}

function GroupSwitcherHarness() {
  const [activeGroupId, setActiveGroupId] = useState('math-continuing')
  return (
    <div className="max-w-xl space-y-3">
      <CourseGroupSwitcher
        activeGroupId={activeGroupId}
        course={mathCourse}
        groups={mathGroups}
        onChange={setActiveGroupId}
      />
      <p role="status" className="text-small text-muted-foreground">
        Активная группа: {mathGroups.find((group) => group.id === activeGroupId)?.name}
      </p>
    </div>
  )
}

export const ActiveAndAllowedGroups: Story = {
  name: 'Active and allowed groups',
  render: () => <GroupSwitcherHarness />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByRole('button', { name: /Продолжающие/ })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    await userEvent.click(canvas.getByRole('button', { name: /Эксперты/ }))
    await expect(canvas.getByRole('status')).toHaveTextContent('Активная группа: Эксперты')
  },
}
