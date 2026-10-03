import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, waitFor, within } from 'storybook/test'

import { reviewAnnotationManifestSchema, type ReviewAnnotationManifest } from '@vmsh/contracts'

import { ReviewAnnotationEditor } from './review-annotation-editor'
import { ReviewAnnotationSurface, ReviewAnnotationViewer } from './review-annotation-surface'

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

const landscapeImage = `data:image/svg+xml,${encodeURIComponent(`
  <svg xmlns="http://www.w3.org/2000/svg" width="1200" height="560">
    <rect width="1200" height="560" fill="#fffdf8"/>
    <rect x="30" y="30" width="1140" height="500" fill="none" stroke="#59616b" stroke-width="4"/>
    <text x="60" y="100" font-size="36">Широкая фотография решения</text>
  </svg>
`)}`

// docs/review-annotation-geometry.md: normalized corners must cover the actual
// image, not a centered square, including after CSS rotation and zoom.
async function expectFullImageCoverage(surface: HTMLElement) {
  await waitFor(async () => {
    const image = surface.querySelector('img')!
    const overlay = surface.querySelector<SVGSVGElement>('svg[data-coordinate-space="image"]')!
    await expect(image.naturalWidth).toBeGreaterThan(0)
    const matrix = overlay.getScreenCTM()!
    await expect(matrix).not.toBeNull()
    const corners = [
      [0, 0],
      [1, 0],
      [0, 1],
      [1, 1],
    ].map(([x, y]) => new DOMPoint(x, y).matrixTransform(matrix))
    const imageBounds = image.getBoundingClientRect()
    const bounds = {
      left: Math.min(...corners.map((point) => point.x)),
      right: Math.max(...corners.map((point) => point.x)),
      top: Math.min(...corners.map((point) => point.y)),
      bottom: Math.max(...corners.map((point) => point.y)),
    }
    for (const edge of ['left', 'right', 'top', 'bottom'] as const) {
      await expect(Math.abs(bounds[edge] - imageBounds[edge])).toBeLessThan(1)
    }
  })
}

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

function AnnotationHarness({ landscape = false }: { landscape?: boolean }) {
  const [manifest, setManifest] = useState<ReviewAnnotationManifest | null>(restoredManifest)
  return (
    <div className="max-w-2xl space-y-3" data-density="staff">
      <ReviewAnnotationEditor
        attachmentId="attachment-review-story"
        imageAlt="Страница решения задачи о ладьях"
        imageSource={landscape ? landscapeImage : evidenceImage}
        initialManifest={restoredManifest}
        onChange={setManifest}
      />
      <p
        className="text-caption text-muted-foreground"
        data-testid="manifest-readout"
        data-marks={JSON.stringify(manifest?.marks ?? [])}
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

    await expectFullImageCoverage(surface)
    await expect(surface).toHaveAttribute('data-rotation', '0')
    await expect(readout).toHaveTextContent('rotation=0; marks=2')

    await userEvent.click(canvas.getByRole('button', { name: 'Повернуть по часовой стрелке' }))
    await expect(surface).toHaveAttribute('data-rotation', '90')
    await expect(readout).toHaveTextContent('rotation=90; marks=2')

    await userEvent.click(canvas.getByRole('button', { name: 'Отменить' }))
    await expect(surface).toHaveAttribute('data-rotation', '0')
    await expectFullImageCoverage(surface)
    await userEvent.click(canvas.getByRole('button', { name: 'Повторить' }))
    await expect(surface).toHaveAttribute('data-rotation', '90')

    await userEvent.click(canvas.getByRole('button', { name: 'Увеличить масштаб' }))
    await expect(surface).toHaveAttribute('data-zoom', '1.5')
    await expectFullImageCoverage(surface)

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
    await expect(JSON.parse(readout.getAttribute('data-marks')!)).toEqual([
      ...restoredManifest.marks,
      expect.objectContaining({ coordinateSpace: 'image' }),
    ])

    // Leave the accepted visual baseline in its readable, unzoomed state.
    await userEvent.click(canvas.getByRole('button', { name: 'Сбросить масштаб' }))
    await userEvent.click(canvas.getByRole('button', { name: 'Отменить' }))
    await userEvent.click(canvas.getByRole('button', { name: 'Отменить' }))
    await expect(surface).toHaveAttribute('data-zoom', '1')
    await expect(surface).toHaveAttribute('data-rotation', '0')
    await expect(readout).toHaveTextContent('rotation=0; marks=2')
    for (let turn = 0; turn < 4; turn += 1) {
      await userEvent.click(canvas.getByRole('button', { name: 'Повернуть по часовой стрелке' }))
      await expectFullImageCoverage(surface)
    }
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
    await expectFullImageCoverage(surface)
    await userEvent.click(canvas.getByRole('button', { name: 'Увеличить масштаб' }))
    await expect(surface).toHaveAttribute('data-zoom', '1.5')
    await expect(canvas.getAllByText('Проверьте этот переход')).toHaveLength(2)
    await userEvent.click(canvas.getByRole('button', { name: 'Сбросить масштаб' }))
    await expect(surface).toHaveAttribute('data-zoom', '1')
  },
}

export const LandscapeEditor: Story = {
  name: 'Широкая фотография: вся площадь доступна для разметки',
  render: () => <AnnotationHarness landscape />,
  play: Editor.play!,
}

export const MobileLandscapeEditor: Story = {
  name: 'Широкая фотография на экране 320px',
  render: () => (
    <div style={{ width: 320 }}>
      <AnnotationHarness landscape />
    </div>
  ),
  play: Editor.play!,
}

const compatibilityMarks = reviewAnnotationManifestSchema.parse({
  ...restoredManifest,
  marks: [
    ...restoredManifest.marks,
    {
      markId: 'legacy-pen',
      kind: 'pencil',
      data: {
        points: [
          { x: 0.1, y: 0.1 },
          { x: 0.8, y: 0.8 },
        ],
        width: 0.008,
        color: 'red',
      },
    },
    {
      markId: 'legacy-erase',
      kind: 'eraser',
      data: {
        points: [
          { x: 0.3, y: 0.3 },
          { x: 0.4, y: 0.4 },
        ],
        width: 0.02,
      },
    },
    {
      markId: 'legacy-arrow',
      kind: 'arrow',
      data: { start: { x: 0.1, y: 0.3 }, end: { x: 0.8, y: 0.3 }, width: 0.008, color: 'blue' },
    },
    {
      markId: 'legacy-highlight',
      kind: 'highlight',
      data: { x: 0.1, y: 0.4, width: 0.7, height: 0.1 },
    },
    {
      markId: 'full-image',
      coordinateSpace: 'image',
      kind: 'rectangle',
      data: { x: 0, y: 0, width: 1, height: 1, strokeWidth: 0.006, color: 'blue' },
    },
  ],
}).marks

export const LegacyGeometry: Story = {
  name: 'Совместимость сохранённых пометок',
  render: () => (
    <div>
      {[320, 960].flatMap((width) =>
        [evidenceImage, landscapeImage].flatMap((source, sourceIndex) =>
          ([0, 90, 180, 270] as const).flatMap((rotation) =>
            [1, 1.5].map((zoom) => (
              <div
                key={`${width}-${sourceIndex}-${rotation}-${zoom}`}
                style={{ width, maxWidth: '100%' }}
              >
                <ReviewAnnotationSurface
                  imageAlt={`Геометрия ${width}-${sourceIndex}-${rotation}-${zoom}`}
                  imageSource={source}
                  marks={compatibilityMarks}
                  rotation={rotation}
                  zoom={zoom}
                  testId="compatibility-canvas"
                  className="max-h-60"
                />
              </div>
            )),
          ),
        ),
      )}
    </div>
  ),
  play: async ({ canvasElement }) => {
    for (const surface of within(canvasElement).getAllByTestId('compatibility-canvas')) {
      await expectFullImageCoverage(surface)
      const overlay = surface.querySelector<SVGSVGElement>('svg[data-coordinate-space="legacy"]')!
      // Build the old renderer beside the current one, using the exact same marks.
      const reference = overlay.cloneNode(true) as SVGSVGElement
      reference.setAttribute('preserveAspectRatio', 'xMidYMid meet')
      reference.style.visibility = 'hidden'
      for (const definition of reference.querySelectorAll('[id]')) {
        const originalId = definition.id
        definition.id = `${originalId}-reference`
        for (const node of reference.querySelectorAll('*')) {
          for (const attr of ['mask', 'clip-path', 'marker-end']) {
            if (node.getAttribute(attr) === `url(#${originalId})`)
              node.setAttribute(attr, `url(#${definition.id})`)
          }
        }
      }
      reference.querySelectorAll('[transform]').forEach((node) => node.removeAttribute('transform'))
      reference.querySelectorAll('[clip-path]').forEach((node) => node.removeAttribute('clip-path'))
      overlay.parentElement!.append(reference)
      try {
        for (const mark of compatibilityMarks.filter(
          (mark) => !mark.coordinateSpace && mark.kind !== 'eraser',
        )) {
          const selector = `[data-mark-id="${mark.markId}"]`
          const actual = overlay.querySelector(selector)!.getBoundingClientRect()
          const previous = reference.querySelector(selector)!.getBoundingClientRect()
          for (const edge of ['left', 'right', 'top', 'bottom'] as const) {
            await expect(
              Math.abs(actual[edge] - previous[edge]),
              `${surface.querySelector('img')?.alt} ${mark.markId} ${edge}: ${JSON.stringify(actual)} vs ${JSON.stringify(previous)}`,
            ).toBeLessThan(1)
          }
        }
        const actualEraser = overlay.querySelector('mask path')!.getBoundingClientRect()
        const previousEraser = reference.querySelector('mask path')!.getBoundingClientRect()
        for (const edge of ['left', 'right', 'top', 'bottom'] as const) {
          await expect(Math.abs(actualEraser[edge] - previousEraser[edge])).toBeLessThan(1)
        }
      } finally {
        reference.remove()
      }
    }
  },
}
