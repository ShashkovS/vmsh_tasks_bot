import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import type { OralWindowJoin, StudentOralWindow } from '@vmsh/contracts'

import { OralAdmission } from './oral-admission'

const meta = {
  title: 'Product/Oral admission',
  component: OralAdmission,
  args: { windows: [] },
  parameters: { layout: 'padded' },
} satisfies Meta<typeof OralAdmission>
export default meta
type Story = StoryObj<typeof meta>

const windows: StudentOralWindow[] = [
  {
    windowId: 'oral-window.1',
    sequenceNumber: 1,
    opensAt: '2026-10-05T11:00:00Z',
    closesAt: '2026-10-05T13:00:00Z',
    joinLabel: 'Подключиться к Zoom',
    state: 'open',
    joinAvailable: true,
    version: 1,
  },
  {
    windowId: 'oral-window.2',
    sequenceNumber: 2,
    opensAt: '2026-10-07T15:00:00Z',
    closesAt: '2026-10-07T17:00:00Z',
    joinLabel: 'Подключиться к Zoom',
    state: 'upcoming',
    joinAvailable: false,
    version: 1,
  },
]

function InteractiveWindows() {
  const [join, setJoin] = useState<OralWindowJoin | null>(null)
  return (
    <div className="max-w-2xl">
      <OralAdmission
        onRevealJoin={(windowId) =>
          setJoin({
            windowId,
            joinLabel: 'Открыть Zoom',
            joinUrl: 'https://zoom.example.test/j/179',
            joinCode: '179179',
            closesAt: '2026-10-05T13:00:00Z',
          })
        }
        revealedJoin={join}
        windows={windows}
      />
    </div>
  )
}

export const Schedule: Story = { render: () => <InteractiveWindows /> }

export const RevealJoinDetails: Story = {
  render: () => <InteractiveWindows />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.click(canvas.getByRole('button', { name: 'Подключиться к Zoom' }))
    await expect(canvas.getByText('Код:')).toBeInTheDocument()
    await expect(canvas.getByRole('link', { name: /Открыть Zoom/ })).toHaveAttribute(
      'href',
      'https://zoom.example.test/j/179',
    )
  },
}

export const NoWindows: Story = { args: { windows: [] } }
