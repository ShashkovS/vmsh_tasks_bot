import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import { reviewAnnotationManifestSchema, type ReviewAnnotationManifest } from '@vmsh/contracts'

import { ReviewAnnotationEditor } from './review-annotation-editor'
import { ReviewAnnotationViewer } from './review-annotation-surface'

const meta = {
  title: 'Product/Review annotation',
  parameters: { layout: 'padded' },
} satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

const evidenceImage = `data:image/svg+xml,${encodeURIComponent(`
  <svg xmlns="http://www.w3.org/2000/svg" width="900" height="1200" viewBox="0 0 900 1200">
    <rect width="900" height="1200" fill="#fffdf8"/>
    <g fill="#25282d" font-family="Georgia, serif" font-size="34">
      <text x="70" y="100">Задача 21н.6. Расстановка ладей</text>
      <text x="70" y="190">Пусть на доске n × n стоят ладьи,</text>
      <text x="70" y="240">не бьющие друг друга.</text>
      <text x="70" y="350">В каждой строке и столбце не более</text>
      <text x="70" y="400">одной ладьи, поэтому ответ n!.</text>
      <path d="M 100 520 C 260 480 410 560 570 510" fill="none" stroke="#59616b" stroke-width="5"/>
      <text x="70" y="650">Осталось проверить крайний случай k = 1.</text>
    </g>
  </svg>
`)}`

const restoredManifest = reviewAnnotationManifestSchema.parse({
  attachmentId: 'attachment-review-story',
  schemaVersion: 1,
  rotation: 0,
  marks: [
    {
      markId: 'annotation-story-rectangle',
      kind: 'rectangle',
      data: { x: 0.06, y: 0.5, width: 0.72, height: 0.08, strokeWidth: 0.006, color: 'red' },
    },
    {
      markId: 'annotation-story-text',
      kind: 'text',
      data: { x: 0.12, y: 0.62, text: 'Проверьте этот переход', size: 0.035, color: 'blue' },
    },
  ],
})

function AnnotationHarness() {
  const [manifest, setManifest] = useState<ReviewAnnotationManifest | null>(restoredManifest)
  return (
    <div className="max-w-2xl space-y-3" data-density="staff">
      <ReviewAnnotationEditor
        attachmentId="attachment-review-story"
        imageAlt="Страница решения задачи о ладьях"
        imageSource={evidenceImage}
        initialManifest={restoredManifest}
        onChange={setManifest}
      />
      <p
        className="text-caption text-muted-foreground"
        data-testid="manifest-readout"
        role="status"
      >
        {manifest
          ? `rotation=${manifest.rotation}; marks=${manifest.marks.length}`
          : 'Разметка пуста'}
      </p>
    </div>
  )
}

/**
 * Phase 6: the original evidence never changes; normalized marks, rotation and
 * history remain aligned while zoom is local viewer state.
 */
export const Editor: Story = {
  name: 'Редактор поверх неизменяемой фотографии',
  render: () => <AnnotationHarness />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const surface = canvas.getByTestId('annotation-canvas')
    const readout = canvas.getByTestId('manifest-readout')

    await expect(surface).toHaveAttribute('data-rotation', '0')
    await expect(readout).toHaveTextContent('rotation=0; marks=2')

    await userEvent.click(canvas.getByRole('button', { name: 'Повернуть по часовой стрелке' }))
    await expect(surface).toHaveAttribute('data-rotation', '90')
    await expect(readout).toHaveTextContent('rotation=90; marks=2')

    await userEvent.click(canvas.getByRole('button', { name: 'Отменить' }))
    await expect(surface).toHaveAttribute('data-rotation', '0')
    await userEvent.click(canvas.getByRole('button', { name: 'Повторить' }))
    await expect(surface).toHaveAttribute('data-rotation', '90')

    await userEvent.click(canvas.getByRole('button', { name: 'Увеличить масштаб' }))
    await expect(surface).toHaveAttribute('data-zoom', '1.5')

    await userEvent.click(canvas.getByRole('button', { name: 'Прямоугольник' }))
    const drawing = canvas.getByRole('application', { name: 'Область разметки фотографии' })
    const bounds = drawing.getBoundingClientRect()
    await userEvent.pointer([
      {
        keys: '[MouseLeft>]',
        target: drawing,
        coords: {
          clientX: bounds.left + bounds.width * 0.2,
          clientY: bounds.top + bounds.height * 0.2,
        },
      },
      {
        target: drawing,
        coords: {
          clientX: bounds.left + bounds.width * 0.45,
          clientY: bounds.top + bounds.height * 0.35,
        },
      },
      { keys: '[/MouseLeft]', target: drawing },
    ])
    await expect(readout).toHaveTextContent('rotation=90; marks=3')

    // Leave the accepted visual baseline in its readable, unzoomed state.
    await userEvent.click(canvas.getByRole('button', { name: 'Сбросить масштаб' }))
    await userEvent.click(canvas.getByRole('button', { name: 'Отменить' }))
    await userEvent.click(canvas.getByRole('button', { name: 'Отменить' }))
    await expect(surface).toHaveAttribute('data-zoom', '1')
    await expect(surface).toHaveAttribute('data-rotation', '0')
    await expect(readout).toHaveTextContent('rotation=0; marks=2')
  },
}

export const ReadOnlyStudentView: Story = {
  render: () => (
    <div className="mx-auto max-w-xl space-y-3">
      <p className="text-small text-muted-foreground">
        Исходная фотография сохранена без изменений. Пометки преподавателя показаны отдельным слоем.
      </p>
      <ReviewAnnotationViewer
        imageAlt="Первая страница решения с пометками преподавателя"
        imageSource={evidenceImage}
        manifest={restoredManifest}
      />
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const surface = canvas.getByTestId('review-annotation-viewer-canvas')
    await expect(surface).toHaveAttribute('data-rotation', '0')
    await userEvent.click(canvas.getByRole('button', { name: 'Увеличить масштаб' }))
    await expect(surface).toHaveAttribute('data-zoom', '1.5')
    await expect(canvas.getAllByText('Проверьте этот переход')).toHaveLength(2)
    await userEvent.click(canvas.getByRole('button', { name: 'Сбросить масштаб' }))
    await expect(surface).toHaveAttribute('data-zoom', '1')
  },
}
