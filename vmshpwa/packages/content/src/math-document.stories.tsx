import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, waitFor } from 'storybook/test'

import { MathDocument, MathHtml } from './index'

const sampleHtml = `
  <p><strong>Задача 21н.6.</strong> Найдите все натуральные числа $n$, для которых</p>
  <p>\\[n^2 + 179 = k^2.\\]</p>
  <ol>
    <li>Объясните, почему числа $k-n$ и $k+n$ имеют одинаковую чётность.</li>
    <li>Переберите возможные разложения числа $179$.</li>
  </ol>
`

function ClientKatexExample() {
  return (
    <MathDocument
      title="Листок для продолжающих"
      className="mx-auto max-w-3xl rounded-lg border bg-card p-6"
    >
      <MathHtml html={sampleHtml} />
    </MathDocument>
  )
}

const meta = {
  title: 'Product/Mathematical document',
  component: ClientKatexExample,
} satisfies Meta<typeof ClientKatexExample>

export default meta
type Story = StoryObj<typeof meta>

export const ClientKaTeX: Story = {
  play: async ({ canvasElement }) => {
    await waitFor(() => expect(canvasElement.querySelectorAll('.katex').length).toBeGreaterThan(1))
  },
}
