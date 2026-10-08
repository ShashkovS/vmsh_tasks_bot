import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, userEvent, within } from 'storybook/test'
import fixture from '@vmsh/contracts/fixtures/content/web-document.v1.json'
import { webContentContractFixtureSchema, type WebContentDocument } from '@vmsh/contracts'
import { StaffWorksheetPreview } from './staff-worksheet-preview'

const parsed = webContentContractFixtureSchema.parse(fixture).document
const condition: WebContentDocument = {
  ...parsed,
  title: null,
  introduction: [],
  materialKind: 'condition',
  problems: [
    {
      ...parsed.problems[0]!,
      ordinal: 1,
      taskReference: '1э.1',
      title: null,
      blocks: [
        {
          type: 'paragraph',
          children: [
            {
              type: 'text',
              value:
                'В меню кафе 4 вида пирожных и 5 видов чая. Сколькими способами можно сделать заказ из',
            },
          ],
        },
        ...['а', 'б'].map((label) => ({
          type: 'subpart' as const,
          label,
          taskReference: `1э.1${label}`,
          title: `Пирожное и чай — ${label}`,
          blocks: [
            {
              type: 'paragraph' as const,
              children: [{ type: 'text' as const, value: 'одного пирожного и одного чая;' }],
            },
          ],
        })),
      ],
    },
  ],
}
const figure = parsed.problems
  .flatMap((problem) => problem.blocks)
  .find((block) => block.type === 'figure')
if (figure?.type === 'figure' && figure.asset.status === 'available') {
  condition.problems[0]!.preambleBlocks = [
    { ...figure, asset: { ...figure.asset, src: '/content/geometry.svg' } },
  ]
}
const hint: WebContentDocument = {
  ...condition,
  materialKind: 'hint',
  problems: condition.problems.map((problem) => ({
    ...problem,
    blocks: [
      {
        type: 'paragraph',
        children: [
          { type: 'text', value: 'Попробуйте решить задачу для ' },
          { type: 'math', latex: '3\\times2', display: false },
          { type: 'text', value: ' вариантов.' },
        ],
      },
    ],
  })),
}
const meta = {
  title: 'Pages/Staff/Worksheet preview',
  component: StaffWorksheetPreview,
  args: { condition, document: hint, submissionClosed: false },
} satisfies Meta<typeof StaffWorksheetPreview>
export default meta
type Story = StoryObj<typeof meta>
export const Hints: Story = {
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByRole('heading', { name: 'Задача 1э.1.' })).toBeVisible()
    await expect(canvas.queryByText('Задача 1э.1а.', { exact: false })).toBeNull()
    await expect(canvasElement.querySelector('.vmsh-subpart-label')).toHaveTextContent(
      '1а) «Пирожное и чай — а»',
    )
    await expect(canvas.getAllByRole('button', { name: 'Открыть' })[0]).toBeDisabled()
    const buttons = canvas.getAllByRole('button', { name: 'Скрыть подсказку' })
    await expect(buttons).toHaveLength(2)
    await userEvent.click(buttons[0]!)
    await expect(canvas.getAllByRole('button', { name: 'Скрыть подсказку' })).toHaveLength(1)
  },
}
export const Conditions: Story = { args: { document: condition } }
export const Solutions: Story = {
  args: { document: { ...hint, materialKind: 'solution' }, submissionClosed: true },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.queryByRole('button', { name: 'Ответить' })).toBeNull()
    await expect(canvas.getAllByRole('button', { name: 'Скрыть решение' })).toHaveLength(2)
  },
}
