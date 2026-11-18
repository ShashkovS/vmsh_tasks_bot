import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import { Button } from '@vmsh/ui'

import { ContentUpdateMarker } from './content-update-marker'

const meta = {
  title: 'Product/Content/Realtime replacement marker',
  component: ContentUpdateMarker,
} satisfies Meta<typeof ContentUpdateMarker>

export default meta
type Story = StoryObj<typeof meta>

function ReplacementScenario() {
  const [visible, setVisible] = useState(false)
  return (
    <div className="max-w-xl rounded-md bg-background p-4 text-foreground">
      <ContentUpdateMarker visible={visible} />
      <p className="mb-4 font-reading">Здесь остаётся открытым опубликованный материал.</p>
      <Button onClick={() => setVisible(true)} size="sm" variant="outline">
        Имитировать обновление
      </Button>
    </div>
  )
}

export const CalmRealtimeReplacement: Story = {
  name: 'Realtime replacement → calm marker',
  args: { visible: false },
  render: () => <ReplacementScenario />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.queryByRole('status')).not.toBeInTheDocument()
    await userEvent.click(canvas.getByRole('button', { name: 'Имитировать обновление' }))
    await expect(canvas.getByRole('status')).toHaveTextContent(
      /Материал обновлён.*Открыта новая опубликованная версия\./s,
    )
  },
}
