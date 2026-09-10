import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within, waitFor } from 'storybook/test'
import type { LiveBoard } from '@vmsh/contracts'
import { studentNameMatchesSearch } from './student-directory-search'
import { LiveSchoolGrid, LiveZoomGrid } from './live-marking-grid'

const board: LiveBoard = {
  schemaVersion: 1,
  requestId: 'story',
  lesson: { lessonId: 'gl-1', number: 1, groupId: 'g-1', groupName: 'Начальный' },
  students: ['Анна Белова', 'Борис Ветров', 'Ирина Орлова'].map((displayName, i) => ({
    studentId: `u-${i}`,
    displayName,
    middleName: 'Александровна',
    grade: 6,
    groupId: 'g-1',
    groupName: 'Начальный',
    attendanceMode: 'in_person',
    enrollmentVersion: 1,
    attendance: 'unmarked',
    attendanceVersion: 0,
  })),
  problems: Array.from({ length: 24 }, (_, i) => ({
    problemId: `p-${i}`,
    label: i < 20 ? `${i + 1}` : `${21 + Math.floor((i - 20) / 2)}${i % 2 ? 'б' : 'а'}`,
    title: 'Расскажите решение',
    oral: true,
    number: i + 1,
  })),
  planId: 'cap-1',
  readOnly: false,
  visit: null,
}
function Harness({
  zoom = false,
  status,
  large = false,
  few = false,
}: {
  zoom?: boolean
  status?: 'queued' | 'conflict'
  large?: boolean
  few?: boolean
}) {
  const [condition, setCondition] = useState('')
  const [expanded, setExpanded] = useState<string | null>(null)
  const [marks, setMarks] = useState<Record<string, number>>({})
  const props = {
    board: large
      ? {
          ...board,
          students: Array.from({ length: 200 }, (_, i) => ({
            ...board.students[0]!,
            studentId: `u-${i}`,
            displayName: `Ученик ${i}`,
          })),
          problems: Array.from({ length: 50 }, (_, i) => ({
            ...board.problems[0]!,
            problemId: `p-${i}`,
            label: `${i + 1}`,
            number: i + 1,
          })),
        }
      : few
        ? { ...board, problems: board.problems.slice(0, 1) }
        : board,
    display: (s: string, p: string) => ({
      symbol: ['', '+', '−'][marks[`${s}:${p}`] ?? 0]!,
      mine: !!marks[`${s}:${p}`],
      changed: !!marks[`${s}:${p}`],
      pending: status,
      disabled: false,
    }),
    onMark: (s: string, p: string) =>
      setMarks((m) => ({ ...m, [`${s}:${p}`]: ((m[`${s}:${p}`] ?? 0) + 1) % 3 })),
  }
  return (
    <div className="flex h-[480px] flex-col">
      {zoom ? (
        <>
          <LiveZoomGrid {...props} onCondition={(p) => setCondition(p.label)} />
          <output aria-label="Открыто условие">{condition}</output>
        </>
      ) : (
        <LiveSchoolGrid
          {...props}
          expanded={expanded}
          onExpand={(s) => setExpanded(expanded === s ? null : s)}
          onAttendance={() => undefined}
          attendance={() => ({ value: 'unmarked', pending: false, disabled: false })}
        />
      )}
    </div>
  )
}
const meta = {
  title: 'Pages/Staff/Live marking',
  component: Harness,
  parameters: { layout: 'fullscreen' },
} satisfies Meta<typeof Harness>
export default meta
type Story = StoryObj<typeof meta>
export const Classroom: Story = {
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.click(canvas.getByRole('button', { name: 'Анна Белова' }))
    await expect(
      canvas.getByRole('button', { name: /Анна Белова.*Александровна/ }),
    ).toHaveAttribute('aria-expanded', 'true')
    const cell = canvas.getByRole('button', { name: /Анна Белова, задача 1:/ })
    await userEvent.click(cell)
    await expect(cell).toHaveAccessibleName(/\+/)
  },
}
export const Zoom: Story = {
  args: { zoom: true },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const marks = canvas.getAllByRole('button', { name: /^Задача / })
    await expect(marks).toHaveLength(24)
    await expect(marks[0]!.getBoundingClientRect().top).toBe(marks[1]!.getBoundingClientRect().top)
    await userEvent.click(canvas.getByRole('button', { name: 'Показать условие задачи 21б' }))
    await expect(canvas.getByLabelText('Открыто условие')).toHaveTextContent('21б')
    await expect(canvas.getByRole('button', { name: /^Задача 21б:/ })).toHaveAccessibleName(/пусто/)
  },
}
export const Offline: Story = { args: { status: 'queued' } }
export const Conflict: Story = { args: { status: 'conflict' } }

export const LargeClassroom: Story = {
  args: { large: true },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const cell = canvas.getByRole('button', { name: /^Ученик 0, задача 1:/ })
    const samples: number[] = []
    for (let i = 0; i < 20; i++) {
      const latency = await new Promise<number>((resolve) => {
        const observer = new MutationObserver(() => {
          observer.disconnect()
          resolve(performance.now() - start)
        })
        observer.observe(cell, { attributes: true, attributeFilter: ['aria-label'] })
        const start = performance.now()
        cell.click()
      })
      await waitFor(() =>
        expect(cell).toHaveAccessibleName(new RegExp(['\\+', '−', 'пусто'][i % 3]!)),
      )
      samples.push(latency)
    }
    samples.sort((a, b) => a - b)
    console.info(`Live marking 200x50 click p95: ${samples[18]!.toFixed(1)}ms`)
    await expect(samples[18]).toBeLessThan(50)
    await expect(canvas.getAllByRole('row').length).toBeLessThan(40)
    const names = Array.from({ length: 2000 }, (_, i) => `Петров${i} Александр Иванович`)
    const start = performance.now()
    names.filter((name) => studentNameMatchesSearch(name, 'Петроо Александр'))
    const duration = performance.now() - start
    console.info(`Live marking fuzzy 2000: ${duration.toFixed(1)}ms`)
    await expect(duration).toBeLessThan(100)
  },
}

export const OneProblemClassroom: Story = {
  args: { few: true },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await waitFor(() => expect(canvas.getAllByRole('rowheader').length).toBeGreaterThan(0))
    await expect(
      canvas.getAllByRole('rowheader')[0]!.getBoundingClientRect().width,
    ).toBeLessThanOrEqual(161)
  },
}
