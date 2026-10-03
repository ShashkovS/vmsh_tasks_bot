import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, fn, userEvent, within } from 'storybook/test'
import { WorksheetMaterials } from './worksheet-materials'
const meta = {
  title: 'Product/Worksheet materials',
  component: WorksheetMaterials,
  args: {
    hint: {
      available: true,
      confirmationRequired: true,
      load: fn(() => Promise.resolve(<p>Подсказка загружена</p>)),
    },
    solution: { available: true, load: fn(() => Promise.resolve(<p>Решение загружено</p>)) },
  },
} satisfies Meta<typeof WorksheetMaterials>
export default meta
type Story = StoryObj<typeof meta>
export const Confirmation: Story = {
  play: async ({ canvasElement, args }) => {
    const canvas = within(canvasElement)
    await userEvent.click(canvas.getByRole('button', { name: 'Подсказка' }))
    await expect(args.hint.load).not.toHaveBeenCalled()
    await userEvent.click(canvas.getByRole('button', { name: 'Отмена' }))
    await expect(args.hint.load).not.toHaveBeenCalled()
    await userEvent.click(canvas.getByRole('button', { name: 'Подсказка' }))
    await userEvent.click(canvas.getByRole('button', { name: 'Показать подсказку' }))
    await expect(canvas.getByText('Подсказка загружена')).toBeVisible()
    await userEvent.click(canvas.getByRole('button', { name: 'Скрыть подсказку' }))
    await userEvent.click(canvas.getByRole('button', { name: 'Подсказка' }))
    await expect(args.hint.load).toHaveBeenCalledOnce()
  },
}
export const Solution: Story = {
  play: async ({ canvasElement, args }) => {
    const canvas = within(canvasElement)
    await userEvent.click(canvas.getByRole('button', { name: 'Решение' }))
    await expect(canvas.getByText('Решение загружено')).toBeVisible()
    await expect(args.solution.load).toHaveBeenCalledOnce()
  },
}
