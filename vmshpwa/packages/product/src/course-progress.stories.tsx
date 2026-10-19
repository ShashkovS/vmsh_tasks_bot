import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import { Card, CardContent } from '@vmsh/ui'

import { CourseContext } from './course-context'
import { mathCourse, physicsCourse } from './course-fixtures'
import { StrengthTrend, type StrengthLessonPoint } from './progress-charts'
import { StudentProgress } from './student-progress'

const meta = {
  title: 'Product/Progress',
  parameters: { layout: 'padded' },
} satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

const courseData: Record<
  string,
  { solved: number; attempted: number; points: StrengthLessonPoint[] }
> = {
  [mathCourse.id]: {
    solved: 18,
    attempted: 31,
    points: [
      { lesson: '39', simple: 7.1, complex: 4.6, solved: '6/12', group: 'н' },
      { lesson: '40', simple: 8, complex: 5.1, solved: '8/14', group: 'н' },
      { lesson: '41', simple: 8.4, complex: 5.4, solved: '4/12', group: 'п' },
    ],
  },
  [physicsCourse.id]: {
    solved: 6,
    attempted: 9,
    points: [
      { lesson: '7', simple: 5.8, complex: 2.7, solved: '2/4', group: 'вв' },
      { lesson: '8', simple: 6.4, complex: 3.5, solved: '3/4', group: 'вв' },
      { lesson: '9', simple: 6.9, complex: 3.9, solved: '1/3', group: 'вв' },
    ],
  },
}

function CoursesSeparatedHarness() {
  const [courseId, setCourseId] = useState(mathCourse.id)
  const course = courseId === mathCourse.id ? mathCourse : physicsCourse
  const data = courseData[courseId]!
  return (
    <div className="max-w-3xl space-y-4">
      <CourseContext
        activeCourseId={courseId}
        courses={[mathCourse, physicsCourse]}
        onCourseChange={setCourseId}
      />
      <Card>
        <CardContent className="space-y-4 pt-5">
          <h2 className="text-section font-semibold text-foreground">{course.name}</h2>
          <StudentProgress attemptedCount={data.attempted} solvedCount={data.solved} />
          <StrengthTrend
            caption={`Личная динамика только по курсу «${course.name}».`}
            points={data.points}
          />
        </CardContent>
      </Card>
      <p className="text-caption text-muted-foreground">
        Результаты, streak и достижения курсов не складываются и не сравниваются с группой.
      </p>
    </div>
  )
}

export const CoursesSeparated: Story = {
  name: 'Courses separated',
  render: () => <CoursesSeparatedHarness />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByText(/задач зачтено/)).toHaveTextContent('18 задач зачтено')
    await userEvent.selectOptions(canvas.getByLabelText('Курс'), physicsCourse.id)
    await expect(canvas.getByText(/задач зачтено/)).toHaveTextContent('6 задач зачтено')
    await expect(canvas.queryByText(/место|процентиль|медиана/i)).not.toBeInTheDocument()
  },
}
