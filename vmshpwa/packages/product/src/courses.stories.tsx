import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import {
  CourseCard,
  CourseGroupSwitcher,
  CourseNotificationSettings,
  type CourseNotificationPreference,
} from './course-context'
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

export const AllowedGroupReadingContext: Story = {
  name: 'Allowed group reading context',
  render: () => (
    <div className="max-w-xl">
      <CourseGroupSwitcher
        activeGroupId="math-beginner"
        course={mathCourse}
        groups={mathGroups}
        helpText="Можно читать опубликованные листки всех доступных вам групп. Активная группа курса от этого не меняется."
      />
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByText(/Активная группа курса от этого не меняется/)).toBeVisible()
  },
}

function CourseNotificationsHarness() {
  const [preferences, setPreferences] = useState<CourseNotificationPreference[]>([
    {
      course: mathCourse,
      category: 'news',
      label: 'Новые публикации',
      enabled: true,
      inherited: true,
    },
    {
      course: physicsCourse,
      category: 'review_completed',
      label: 'Проверка завершена',
      enabled: false,
      inherited: false,
    },
  ])
  return (
    <div className="max-w-xl">
      <CourseNotificationSettings
        onReset={(courseId, category) =>
          setPreferences((current) =>
            current.map((preference) =>
              preference.course.id === courseId && preference.category === category
                ? { ...preference, enabled: true, inherited: true }
                : preference,
            ),
          )
        }
        onToggle={(courseId, category, enabled) =>
          setPreferences((current) =>
            current.map((preference) =>
              preference.course.id === courseId && preference.category === category
                ? { ...preference, enabled, inherited: false }
                : preference,
            ),
          )
        }
        preferences={preferences}
      />
    </div>
  )
}

export const CourseNotificationOverrides: Story = {
  name: 'Course notification overrides',
  render: () => <CourseNotificationsHarness />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const mathNews = canvas.getByRole('switch', {
      name: 'Новые публикации, Математика 5–7',
    })
    await userEvent.click(mathNews)
    await expect(mathNews).not.toBeChecked()
    await userEvent.click(canvas.getAllByRole('button', { name: 'Общая' })[0]!)
    await expect(mathNews).toBeChecked()
  },
}
