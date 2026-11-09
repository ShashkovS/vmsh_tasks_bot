import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, fn, userEvent, within } from 'storybook/test'
import { teacherWorkReportSchema } from '@vmsh/contracts'
import { PageStatePanel } from '@vmsh/app-shell'
import { TeacherWorkReportView } from './teacher-work-page'

// docs/teacher-work.md: zero, partial, manual/stale, real weekdays and 3 TSV headers.
const columns = ['Шк', 'Пн', 'Вт', 'Ср', 'Вс', '✏'].map((label, i) => ({
  key: `2:${i}`,
  lesson: 2,
  kind: i === 0 ? 'school' : i === 5 ? 'written' : 'zoom',
  date: `2026-09-${i === 5 || i === 4 ? '20' : 14 + i}`,
  label,
}))
const data = teacherWorkReportSchema.parse({
  run: {
    id: 1,
    state: 'completed',
    startedAt: '2026-10-09T10:00:00Z',
    completedAt: '2026-10-09T10:01:00Z',
    errorCode: null,
  },
  operation: null,
  lessons: [{ number: 2, anchor: '2026-09-14' }],
  columns,
  rows: [
    {
      teacherId: 'u-1',
      id: 1,
      surname: 'Загаринский',
      name: 'Александр',
      middlename: 'Валентинович',
      counts: { school: 1, zoom: 3, written: 1 },
      totals: { school: 2.3, zoom: null, written: 3.45 },
      totalHours: null,
      cells: columns.map((column, i) => ({
        columnKey: column.key,
        keys: [`${column.kind}:1:${i === 5 ? 2 : column.date}`],
        hours: i === 3 ? null : i === 1 ? 0 : 2.3,
        sources: [i === 0 ? 'manual' : i === 5 ? 'series' : 'log'],
        stale: i === 0,
        anomalies: i === 3 ? ['missing_join'] : [],
      })),
    },
  ],
  tsv: '1\t2\t3\n\t\t2\nid\tsurname\tname\n1\tЗагаринский\tАлександр\n',
})
const meta = {
  title: 'Pages/Staff/Teacher work',
  component: TeacherWorkReportView,
  parameters: { layout: 'fullscreen' },
  decorators: [
    (Story) => (
      <div className="p-4">
        <Story />
      </div>
    ),
  ],
  args: { report: data, onCell: fn() },
} satisfies Meta<typeof TeacherWorkReportView>
export default meta
type Story = StoryObj<typeof meta>
export const Report: Story = {
  play: async ({ canvasElement, args }) => {
    const canvas = within(canvasElement)
    const cell = canvas.getByRole('button', { name: /Загаринский Александр, занятие 2, Шк/ })
    await userEvent.click(cell)
    await expect(args.onCell).toHaveBeenCalledWith('school:1:2026-09-14')
    await expect(canvas.getByText('2.3 *')).toBeVisible()
    await expect(canvas.getByText('— !')).toBeVisible()
  },
}
export const Empty: Story = { args: { report: { ...data, rows: [] } } }
export const NoSnapshot: Story = { args: { report: { ...data, run: null, rows: [] } } }
export const Dark: Story = { globals: { theme: 'dark' } }
export const Loading: Story = { render: () => <PageStatePanel state="loading" /> }
export const Error: Story = { render: () => <PageStatePanel state="error" /> }
export const Offline: Story = { render: () => <PageStatePanel state="offline" /> }
export const Forbidden: Story = { render: () => <PageStatePanel state="forbidden" /> }
