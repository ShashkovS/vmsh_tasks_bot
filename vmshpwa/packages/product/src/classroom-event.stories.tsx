import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import { mathCourse, mathGroups, physicsCourse, physicsGroups } from './course-fixtures'
import { InPersonEventComposer, type InPersonGroupLessonView } from './in-person-event'

const meta = {
  title: 'Product/Classrooms',
  parameters: { layout: 'padded' },
} satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

const initialLessons: InPersonGroupLessonView[] = [
  {
    id: 'math-beginner-41',
    course: mathCourse,
    group: mathGroups[0]!,
    lessonNumber: 41,
    inPersonCount: 84,
    assignedCount: 82,
    inheritedRooms: ['201', '202', '203', '204', '205', '206'],
    selected: true,
  },
  {
    id: 'math-continuing-41',
    course: mathCourse,
    group: mathGroups[1]!,
    lessonNumber: 41,
    inPersonCount: 68,
    assignedCount: 68,
    inheritedRooms: ['301', '302', '303', '304', '305'],
    selected: true,
  },
  {
    id: 'physics-intro-9',
    course: physicsCourse,
    group: physicsGroups[0]!,
    lessonNumber: 9,
    inPersonCount: 24,
    assignedCount: 23,
    inheritedRooms: ['401', '402'],
    selected: false,
  },
]

function EventHarness() {
  const [lessons, setLessons] = useState(initialLessons)
  return (
    <InPersonEventComposer
      groupLessons={lessons}
      onToggle={(id, selected) =>
        setLessons((current) =>
          current.map((lesson) => (lesson.id === id ? { ...lesson, selected } : lesson)),
        )
      }
      startsAt="1 февраля, 10:00–13:00"
      title="Очное воскресенье"
    />
  )
}

export const MultiCourseInheritedEvent: Story = {
  name: 'Multi-course inherited event',
  render: () => <EventHarness />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByRole('status')).toHaveTextContent('11 аудиторий и 150 назначений')
    await userEvent.click(canvas.getByRole('checkbox', { name: 'Включить Физика 6–7, Знакомство' }))
    await expect(canvas.getByRole('status')).toHaveTextContent('13 аудиторий и 173 назначения')
  },
}
