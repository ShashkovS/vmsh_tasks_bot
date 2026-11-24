import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, fn, userEvent, waitFor, within } from 'storybook/test'
import fixture from '@vmsh/contracts/fixtures/review/contribution.v1.json'
import { reviewContributionSchema } from '@vmsh/contracts'
import { ReviewContributionView } from './review-contribution'

// docs/review-contribution.md: native disclosure; trusted keyboard input is covered in E2E.
const data = reviewContributionSchema.parse(fixture)
const meta = {
  title: 'Pages/Staff/Personal contribution',
  component: ReviewContributionView,
  args: { data, onRetry: fn(), onSelect: fn() },
  globals: { density: 'staff' },
} satisfies Meta<typeof ReviewContributionView>
export default meta
type Story = StoryObj<typeof meta>

export const Compact: Story = {
  play: async ({ canvasElement, args }) => {
    const canvas = within(canvasElement)
    const summary = canvas.getByText('Ваш вклад').closest('summary')!
    await expect(summary.parentElement).not.toHaveAttribute('open')
    await userEvent.click(summary)
    await waitFor(() => expect(summary.parentElement).toHaveAttribute('open'))
    await expect(canvas.getByRole('progressbar', { name: 'Ваш вклад за занятие' })).toHaveAttribute(
      'aria-valuenow',
      '23',
    )
    await userEvent.selectOptions(canvas.getByLabelText('Занятие статистики'), '10')
    await expect(args.onSelect).toHaveBeenCalledWith({ course: 'c-1', lesson: 10 })
    await userEvent.click(summary)
    await waitFor(() => expect(summary.parentElement).not.toHaveAttribute('open'))
  },
}
export const FailedRefresh: Story = { args: { failed: true } }
export const FailedInitialLoad: Story = { args: { data: undefined, failed: true } }
export const Loading: Story = { args: { data: undefined } }
export const BeforeFirstCheck: Story = {
  args: { data: { ...data, allTime: { ...data.allTime, total: 0, plus: 0 } } },
}
export const MultipleCourses: Story = {
  args: {
    data: {
      ...data,
      lesson: null,
      courses: [...data.courses, { id: 'c-2', name: 'Другой курс', lessons: [4] }],
    },
  },
}
export const RecordAfterBreak: Story = {
  args: { data: { ...data, daily: { ...data.daily, current: 0, periodCount: 0 } } },
}
