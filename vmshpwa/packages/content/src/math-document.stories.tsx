import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, waitFor } from 'storybook/test'

import { MathDocument, MathHtml } from './index'

const sampleHtml = `
  <p><strong>Задача 21н.6.</strong> Найдите все натуральные числа $n$, при которых число
  $n^2 + 179$ является полным квадратом.</p>

  <div class="vmsh-eq" id="eq-nk">
    <div>\\[ n^2 + 179 = k^2, \\qquad k \\in \\mathbb{N}. \\]</div>
    <span class="vmsh-eqno">(1)</span>
  </div>

  <p>Из&nbsp;(<a href="#eq-nk">1</a>) следует $\\left(k-n\\right)\\left(k+n\\right) = 179$, а&nbsp;179 —
  простое число.</p>

  <aside class="vmsh-note">
    <span class="vmsh-note-title">Наблюдение.</span> Числа $k-n$ и $k+n$ имеют одинаковую
    чётность, поэтому оба нечётны.
  </aside>

  <ol>
    <li>Объясните, почему $k - n = 1$, а $k + n = 179$.</li>
    <li>Найдите $n$ и проверьте ответ подстановкой в&nbsp;(1).</li>
  </ol>

  <p>Разложения простого числа на два множителя удобно свести в таблицу:</p>

  <table>
    <thead>
      <tr><th>k − n</th><th>k + n</th><th>k</th><th>n</th><th>Подходит?</th></tr>
    </thead>
    <tbody>
      <tr><td>$1$</td><td>$179$</td><td>$90$</td><td>$89$</td><td>да, $89^2 + 179 = 90^2$</td></tr>
      <tr><td>$179$</td><td>$1$</td><td>$90$</td><td>$-89$</td><td>нет, $n$ не натуральное</td></tr>
    </tbody>
  </table>

  <p>Ответ записывается в поле как одно число: <code>n = 89</code>.</p>
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
    // KaTeX renders inline and display math.
    await waitFor(() => expect(canvasElement.querySelectorAll('.katex').length).toBeGreaterThan(1))
    // The wide table is wrapped for local horizontal scroll, not page scroll.
    await waitFor(() =>
      expect(canvasElement.querySelector('.vmsh-scroll-x > table')).not.toBeNull(),
    )
  },
}
