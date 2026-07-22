/**
 * Exploration/Art direction — phase 1 gate material.
 *
 * These stories are executable proposals, not accepted design. Nothing here is
 * imported by an application; the whole exploration is scoped to `.ad-root` and
 * is deleted or archived once the owner picks a direction (see STATUS.md).
 */
import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, userEvent, within } from 'storybook/test'

import { directionOrder, directions, type DirectionId } from './directions'
import {
  ArtDirectionScene,
  Composer,
  SceneScope,
  Signals,
  StaffWorkspace,
  StudentPhone,
  TaskActions,
  Worksheet,
  type Density,
} from './scene'

import './fonts'
import './exploration.css'

function readDensity(globals: unknown): Density {
  const value = (globals as { density?: unknown }).density
  return value === 'family' || value === 'staff' ? value : 'student'
}

const meta = {
  title: 'Exploration/Art direction',
  component: ArtDirectionScene,
  parameters: {
    layout: 'fullscreen',
    canvasPadding: false,
  },
} satisfies Meta<typeof ArtDirectionScene>

export default meta
type Story = StoryObj<typeof meta>

function scene(direction: DirectionId): Story {
  return {
    args: { direction },
    render: (args, context) => (
      <ArtDirectionScene direction={args.direction} density={readDensity(context.globals)} />
    ),
  }
}

export const OptionAListok: Story = {
  ...scene('a'),
  name: 'A · «Листок»',
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)

    // Раскрытие решения осознанное: панель появляется только по действию.
    const disclosure = canvas.getByRole('button', { name: /Показать решение/ })
    await expect(disclosure).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(disclosure)
    await expect(disclosure).toHaveAttribute('aria-expanded', 'true')
    await expect(canvas.getByLabelText('365 равно 7 умножить на 52 плюс 1')).toBeVisible()

    // Состояние синхронизации меняется текстом, а не только цветом.
    await expect(canvas.getByText(/1 отправка в очереди/)).toBeVisible()
    await userEvent.click(canvas.getByRole('button', { name: 'Показать восстановление связи' }))
    await expect(canvas.getByText(/Сервер принял в 19:47/)).toBeVisible()
  },
}

export const OptionAListokDark: Story = {
  ...scene('a'),
  name: 'A · «Листок» · тёмная',
  globals: { theme: 'dark' },
}

export const OptionBMasterskaya: Story = { ...scene('b'), name: 'B · «Мастерская»' }

export const OptionBMasterskayaDark: Story = {
  ...scene('b'),
  name: 'B · «Мастерская» · тёмная',
  globals: { theme: 'dark' },
}

export const OptionCArhiv: Story = { ...scene('c'), name: 'C · «Архив»' }

export const OptionCArhivDark: Story = {
  ...scene('c'),
  name: 'C · «Архив» · тёмная',
  globals: { theme: 'dark' },
}

/* ------------------------------------------------------------ сравнение */

function CompareColumn({ direction, density }: { direction: DirectionId; density: Density }) {
  const meta = directions[direction]
  return (
    <SceneScope value={meta.name}>
      <div className="ad-root ad-compare__col" data-ad={direction} data-density={density}>
        <div className="ad-compare__head">
          <h2>{meta.name}</h2>
          <p>{meta.focus}</p>
        </div>
        <div className="ad-compare__body">
          <StudentPhone direction={direction} />
          <Worksheet />
          <TaskActions />
          <Composer />
          <div className="ad-root" data-ad={direction} data-density="staff">
            <StaffWorkspace />
          </div>
          <Signals />
        </div>
      </div>
    </SceneScope>
  )
}

function Comparison({ density }: { density: Density }) {
  return (
    <div className="ad-root" data-ad="a" data-density={density}>
      <h1 style={{ margin: 0, padding: '1.5rem 1rem 0', fontSize: '1.25rem' }}>
        Три направления на одинаковом содержании
      </h1>
      <div className="ad-compare ad-compare--3">
        {directionOrder.map((direction) => (
          <CompareColumn density={density} direction={direction} key={direction} />
        ))}
      </div>
    </div>
  )
}

export const Comparison3: Story = {
  name: 'Сравнение A / B / C',
  args: { direction: 'a' },
  render: (_args, context) => <Comparison density={readDensity(context.globals)} />,
}

export const Comparison3Dark: Story = {
  name: 'Сравнение A / B / C · тёмная',
  args: { direction: 'a' },
  globals: { theme: 'dark' },
  render: (_args, context) => <Comparison density={readDensity(context.globals)} />,
}
