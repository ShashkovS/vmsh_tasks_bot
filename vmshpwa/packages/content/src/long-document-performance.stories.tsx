import type { Meta, StoryObj } from '@storybook/react-vite'
import { useEffect, useRef, useState } from 'react'
import { expect, fireEvent, userEvent, waitFor, within } from 'storybook/test'

import {
  longDocumentRenderBudgetMs,
  longRealCorpusDocument,
  longRealCorpusExpectedMathCount,
  longRealCorpusExpectedProblemCount,
} from './long-document-performance-fixture'
import { SemanticMathDocument } from './math-document'

function LongDocumentPerformanceProbe() {
  const [started, setStarted] = useState(false)
  const [durationMs, setDurationMs] = useState<number | null>(null)
  const startedAtRef = useRef(0)
  const documentRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!started) return
    let frame = 0

    const observeCompletedRender = () => {
      const expressions = documentRef.current?.querySelectorAll('[data-math-state]') ?? []
      const allSettled =
        expressions.length === longRealCorpusExpectedMathCount &&
        [...expressions].every(
          (expression) => expression.getAttribute('data-math-state') !== 'pending',
        )

      if (allSettled) {
        setDurationMs(performance.now() - startedAtRef.current)
        return
      }
      frame = requestAnimationFrame(observeCompletedRender)
    }

    frame = requestAnimationFrame(observeCompletedRender)
    return () => cancelAnimationFrame(frame)
  }, [started])

  const start = () => {
    startedAtRef.current = performance.now()
    setStarted(true)
  }

  return (
    <main className="min-h-svh bg-background p-4 text-foreground sm:p-6">
      <div className="mx-auto max-w-5xl space-y-4">
        <header className="rounded-lg border bg-card p-4">
          <h1 className="text-xl font-semibold">Бюджет длинного математического листка</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            {longRealCorpusExpectedProblemCount} задач из настоящих листков 39–41 ·{' '}
            {longRealCorpusExpectedMathCount} клиентских формул KaTeX · аварийный предел{' '}
            {longDocumentRenderBudgetMs} мс.
          </p>
          {!started ? (
            <button
              className="mt-3 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
              onClick={start}
              type="button"
            >
              Запустить проверку рендера
            </button>
          ) : durationMs === null ? (
            <p className="mt-3 text-sm" role="status">
              Формулы рендерятся…
            </p>
          ) : (
            <output
              className="mt-3 block text-sm font-medium"
              data-render-duration-ms={durationMs.toFixed(1)}
              data-testid="long-document-duration"
            >
              Рендер завершён за {durationMs.toFixed(1)} мс
            </output>
          )}
        </header>

        {started ? (
          <div ref={documentRef}>
            <SemanticMathDocument
              className="rounded-lg border bg-card p-5 sm:p-8"
              document={longRealCorpusDocument}
            />
          </div>
        ) : null}
      </div>
    </main>
  )
}

const meta = {
  title: 'Product/Mathematical document/Performance',
  component: LongDocumentPerformanceProbe,
  parameters: { canvasPadding: false, layout: 'fullscreen' },
} satisfies Meta<typeof LongDocumentPerformanceProbe>

export default meta
type Story = StoryObj<typeof meta>

export const LongRealCorpusBudget: Story = {
  name: 'Long real corpus render budget',
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.click(canvas.getByRole('button', { name: 'Запустить проверку рендера' }))

    await waitFor(
      async () => {
        await expect(canvasElement.querySelectorAll('[data-math-state="rendered"]')).toHaveLength(
          longRealCorpusExpectedMathCount,
        )
      },
      { timeout: 5_000 },
    )
    await expect(canvasElement.querySelectorAll('[data-math-state="invalid"]')).toHaveLength(0)
    await expect(canvasElement.querySelectorAll('.vmsh-problem')).toHaveLength(
      longRealCorpusExpectedProblemCount,
    )

    const duration = await canvas.findByTestId('long-document-duration')
    const measuredMs = Number(duration.getAttribute('data-render-duration-ms'))
    await expect(measuredMs).toBeGreaterThan(0)
    await expect(measuredMs).toBeLessThanOrEqual(longDocumentRenderBudgetMs)

    await fireEvent.error(canvas.getByAltText('Недоступный SVG в проверке длинного листка'))
    await expect(canvas.getByText('Рисунок недоступен.')).toBeVisible()
    await expect(canvas.getByText('Подпись сохраняется при ошибке загрузки SVG.')).toBeVisible()
  },
}
