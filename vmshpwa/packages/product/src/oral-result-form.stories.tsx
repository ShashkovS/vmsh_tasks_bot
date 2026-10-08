import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import { OralResultForm, type OralMarkValue } from './oral-result-form'

const meta = {
  title: 'Product/Oral administration',
  component: OralResultForm,
  args: {
    students: [],
    problems: [],
    studentId: '',
    marks: {},
    reactionId: null,
    onStudentChange: () => undefined,
    onMarkChange: () => undefined,
    onReactionChange: () => undefined,
    onSubmit: () => undefined,
  },
  parameters: { layout: 'padded' },
} satisfies Meta<typeof OralResultForm>
export default meta
type Story = StoryObj<typeof meta>

const students = [
  { studentId: 'student.1', displayName: 'Анна Белова' },
  { studentId: 'student.2', displayName: 'Борис Ветров' },
  { studentId: 'student.3', displayName: 'Вера Орлова' },
]
const problems = [
  { problemId: 'problem.1', displayNumber: '1', title: 'Расстановка ладей' },
  { problemId: 'problem.2', displayNumber: '2', title: 'Загаданное число' },
  { problemId: 'problem.3', displayNumber: '3', title: 'Разнообразные вагоны' },
]

function Harness() {
  const [studentId, setStudentId] = useState('student.1')
  const [marks, setMarks] = useState<Record<string, OralMarkValue>>({})
  const [reactionId, setReactionId] = useState<number | null>(null)
  const [saved, setSaved] = useState('Не сохранено')
  return (
    <div className="space-y-2">
      <OralResultForm
        marks={marks}
        onMarkChange={(problemId, value) =>
          setMarks((current) => ({ ...current, [problemId]: value }))
        }
        onReactionChange={setReactionId}
        onStudentChange={setStudentId}
        onSubmit={() => setSaved(`${studentId}:${marks['problem.1']}:${reactionId ?? 'none'}`)}
        problems={problems}
        reactionId={reactionId}
        studentId={studentId}
        students={students}
      />
      <p data-testid="oral-result-readout" role="status">
        {saved}
      </p>
    </div>
  )
}

export const CompactRound: Story = {
  render: () => <Harness />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.click(canvas.getByRole('button', { name: '1: Зачтено' }))
    await userEvent.click(canvas.getByRole('button', { name: /Внятно, уверенно/ }))
    await userEvent.click(canvas.getByRole('button', { name: 'Сохранить результаты' }))
    await expect(canvas.getByTestId('oral-result-readout')).toHaveTextContent(
      'student.1:accepted:300',
    )
  },
}

export const EmptyRoster: Story = {
  args: {
    students: [],
    problems: [],
    studentId: '',
    marks: {},
    reactionId: null,
    onStudentChange: () => undefined,
    onMarkChange: () => undefined,
    onReactionChange: () => undefined,
    onSubmit: () => undefined,
  },
}
