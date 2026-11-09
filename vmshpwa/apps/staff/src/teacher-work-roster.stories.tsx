import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, fn, userEvent, within } from 'storybook/test'
import { teacherWorkInputsSchema, teacherWorkPreviewSchema } from '@vmsh/contracts'
import { TeacherWorkRosterView } from './teacher-work-page'

const teachers = [
  { teacherId: 'u-1', id: 1, surname: 'Ероховец', name: 'Елена', middlename: null },
  { teacherId: 'u-2', id: 2, surname: 'Агеев', name: 'Юрий', middlename: null },
  { teacherId: 'u-3', id: 3, surname: 'Агеев', name: 'Николай', middlename: null },
]
const preview = teacherWorkPreviewSchema.parse({
  rows: [
    { rowId: '1', name: 'Ероховец', teacherId: 'u-1', matchKind: 'exact', candidates: [] },
    {
      rowId: '2',
      name: 'Агеев',
      teacherId: null,
      matchKind: 'ambiguous',
      candidates: teachers
        .slice(1)
        .map((t) => ({ teacherId: t.teacherId, label: `${t.surname} ${t.name}`, score: 1 })),
    },
    { rowId: '3', name: 'Левчук', teacherId: null, matchKind: 'unresolved', candidates: [] },
  ].map((r) => ({
    ...r,
    room: '201',
    startsTime: null,
    endsTime: null,
    source: '201: Ероховец, Агеев, Левчук',
  })),
  notes: ['308 -- резерв.'],
  eventCandidates: ['ipe-1'],
  preliminary: false,
  sourceSha256: '',
})
const draftKey = 'teacher-work-roster-story'
const meta = {
  title: 'Pages/Staff/Teacher work roster',
  component: TeacherWorkRosterView,
  parameters: { layout: 'fullscreen' },
  decorators: [
    (Story) => (
      <div className="p-4">
        <Story />
      </div>
    ),
  ],
  beforeEach: () => {
    for (const suffix of ['', ':preview', ':event', ':base'])
      localStorage.removeItem(draftKey + suffix)
  },
  args: {
    inputs: teacherWorkInputsSchema.parse({
      timezone: 'Europe/Moscow',
      shifts: [],
      signatures: [],
      rosters: [],
      settings: { norm_hours: 2.3, version: 0 },
      events: [
        {
          id: 1,
          public_id: 'ipe-1',
          name: 'Очное занятие',
          starts_at: '2026-09-14T13:10:00Z',
          ends_at: '2026-09-14T15:30:00Z',
          version: 1,
        },
      ],
    }),
    teachers,
    saving: false,
    onSave: fn(),
    onPreview: fn(() => Promise.resolve(preview)),
    draftKey,
  },
} satisfies Meta<typeof TeacherWorkRosterView>
export default meta
type Story = StoryObj<typeof meta>
export const ConfirmUniqueAndResolveExceptions: Story = {
  play: async ({ canvasElement, args }) => {
    const canvas = within(canvasElement)
    await userEvent.type(
      canvas.getByLabelText('Распределение из оргчата'),
      '201: Ероховец, Агеев, Левчук',
    )
    await userEvent.click(canvas.getByRole('button', { name: 'Предварительный просмотр' }))
    await expect(await canvas.findByLabelText('Преподаватель для Ероховец')).toHaveValue('u-1')
    await expect(args.onSave).not.toHaveBeenCalled()
    await expect(
      canvas.getByRole('button', { name: 'Подтвердить фактические смены' }),
    ).toBeDisabled()
    await userEvent.click(canvas.getByRole('checkbox', { name: 'Только требуют выбора' }))
    await expect(canvas.queryByLabelText('Преподаватель для Ероховец')).not.toBeInTheDocument()
    await userEvent.click(canvas.getByRole('button', { name: 'Выбрать Агеев Юрий для Агеев' }))
    await userEvent.click(canvas.getByRole('button', { name: 'Исключить все без совпадений (1)' }))
    await expect(canvas.getByRole('status')).toHaveTextContent('Выбрано: 2 из 2.')
    await userEvent.click(canvas.getByRole('button', { name: 'Подтвердить фактические смены' }))
    await expect(args.onSave).toHaveBeenCalledWith(
      expect.objectContaining({
        state: 'confirmed',
        rows: expect.arrayContaining([
          expect.objectContaining({ teacherId: 'u-1' }),
          expect.objectContaining({ teacherId: 'u-2' }),
        ]),
      }),
      expect.any(Function),
    )
  },
}
export const Dark: Story = {
  ...ConfirmUniqueAndResolveExceptions,
  globals: { theme: 'dark' },
}
