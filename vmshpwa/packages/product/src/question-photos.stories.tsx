import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, userEvent, within } from 'storybook/test'
import { useState } from 'react'
import { QuestionPhotoPicker } from './question-photos'
import { SupportComposer } from './support-dialogue'
const meta = { title: 'Product/Question photos', component: QuestionPhotoPicker } satisfies Meta<
  typeof QuestionPhotoPicker
>
export default meta
type Story = StoryObj<typeof meta>
export const Composer: Story = {
  args: { photos: [], onChange: () => {} },
  render: function Example() {
    const [photos, setPhotos] = useState<Blob[]>([])
    const [text, setText] = useState('Не понимаю этот переход.')
    return (
      <div className="max-w-xl p-4">
        <SupportComposer
          value={text}
          onValueChange={setText}
          onSubmit={() => {}}
          submitLabel="Отправить вопрос"
          attachments={(action) => (
            <QuestionPhotoPicker photos={photos} onChange={setPhotos} action={action} />
          )}
        />
      </div>
    )
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByRole('button', { name: 'Выбрать фотографии' })).toBeVisible()
    await expect(canvas.getByRole('button', { name: 'Сделать фотографию' })).toBeVisible()
    const camera = canvasElement.querySelector<HTMLInputElement>('input[capture]')!
    await expect(camera.getAttribute('capture')).toBe('environment')
    // Native canvas makes a valid raster on every browser without external fixtures.
    const image = document.createElement('canvas')
    image.width = 80
    image.height = 60
    const context = image.getContext('2d')!
    context.fillStyle = '#287b91'
    context.fillRect(0, 0, 80, 60)
    const blob = await new Promise<Blob>((resolve) =>
      image.toBlob((value) => resolve(value!), 'image/png'),
    )
    await userEvent.upload(
      canvas.getByLabelText('Выбрать фотографии', { selector: 'input' }),
      new File([blob], 'question.png', { type: 'image/png' }),
    )
    await expect(canvas.getByAltText('Выбранная фотография')).toBeVisible()
    await userEvent.click(canvas.getByRole('button', { name: 'Убрать фотографию 1' }))
    await expect(canvas.queryByAltText('Выбранная фотография')).not.toBeInTheDocument()
    await userEvent.upload(camera, new File([blob], 'camera.png', { type: 'image/png' }))
    await expect(canvas.getByAltText('Выбранная фотография')).toBeVisible()
    const form = canvasElement.querySelector('form')!
    const container = form.parentElement!
    for (const width of [320, 390, 800]) {
      container.style.width = `${width}px`
      const gallery = canvas
        .getByRole('button', { name: 'Выбрать фотографии' })
        .getBoundingClientRect()
      const cameraButton = canvas
        .getByRole('button', { name: 'Сделать фотографию' })
        .getBoundingClientRect()
      const send = canvas.getByRole('button', { name: 'Отправить вопрос' }).getBoundingClientRect()
      await expect(
        Math.abs(gallery.top + gallery.height / 2 - send.top - send.height / 2),
      ).toBeLessThan(1)
      await expect(cameraButton.right).toBeLessThanOrEqual(send.left)
      await expect(send.right).toBeLessThanOrEqual(form.getBoundingClientRect().right + 1)
    }
  },
}
