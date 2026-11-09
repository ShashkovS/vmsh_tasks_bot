import type { Meta, StoryObj } from '@storybook/react-vite'
import { useMemo, useState } from 'react'
import { expect, userEvent, waitFor, within } from 'storybook/test'

import lesson39Fixture from '@vmsh/contracts/fixtures/content/golden/lesson-39-n.v1.json'
import lesson40Fixture from '@vmsh/contracts/fixtures/content/golden/lesson-40-n.v1.json'
import lesson41Fixture from '@vmsh/contracts/fixtures/content/golden/lesson-41-n.v1.json'
import {
  goldenContentComparisonFixtureSchema,
  type GoldenContentComparisonFixture,
} from '@vmsh/contracts'

import lesson39Pdf from '../../../../_vmsh_examples/usl-39-n.pdf?url'
import lesson40Pdf from '../../../../_vmsh_examples/usl-40-n.pdf?url'
import lesson41Pdf from '../../../../_vmsh_examples/usl-41-n.pdf?url'
import { MathHtml, SemanticMathDocument } from './index'

type DerivativeKind = 'pwa' | 'telegram' | 'pdf'

interface CorpusEntry {
  fixture: GoldenContentComparisonFixture
  pdfUrl: string
}

const corpus: CorpusEntry[] = [
  { fixture: goldenContentComparisonFixtureSchema.parse(lesson39Fixture), pdfUrl: lesson39Pdf },
  { fixture: goldenContentComparisonFixtureSchema.parse(lesson40Fixture), pdfUrl: lesson40Pdf },
  { fixture: goldenContentComparisonFixtureSchema.parse(lesson41Fixture), pdfUrl: lesson41Pdf },
]

const derivativeLabels: Record<DerivativeKind, string> = {
  pwa: 'PWA',
  telegram: 'Telegram Rich',
  pdf: 'PDF',
}

function telegramHtmlForBrowserPreview(html: string): string | null {
  const converted = html
    .replace(
      /<tg-math-block>([\s\S]*?)<\/tg-math-block>/gu,
      (_match, latex: string) => String.raw`<div>\[${latex}\]</div>`,
    )
    .replace(
      /<tg-math>([\s\S]*?)<\/tg-math>/gu,
      (_match, latex: string) => String.raw`<span>\(${latex}\)</span>`,
    )
  return /<\/?tg-/iu.test(converted) ? null : converted
}

function TelegramDerivative({ fixture }: { fixture: GoldenContentComparisonFixture }) {
  const previewHtml = useMemo(
    () => telegramHtmlForBrowserPreview(fixture.telegram.html),
    [fixture.telegram.html],
  )

  return (
    <div className="mx-auto grid max-w-3xl gap-4">
      <section
        aria-label={`Telegram-превью занятия ${fixture.lessonNumber}`}
        className="rounded-lg border bg-card p-5 shadow-sm"
      >
        {previewHtml ? (
          <MathHtml html={previewHtml} />
        ) : (
          <p role="alert">Этот Telegram Rich dialect пока нельзя показать в browser preview.</p>
        )}
      </section>
      <details className="rounded-lg border bg-muted/40 p-4">
        <summary className="cursor-pointer font-medium">Точный Telegram Rich HTML</summary>
        <pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap break-words text-xs">
          <code>{fixture.telegram.html}</code>
        </pre>
      </details>
    </div>
  )
}

/**
 * Manual visual gate required by `docs/testing-strategy.md`: the three real
 * beginner sheets share exact source hashes across PWA/Telegram fixtures, while
 * the PDF tab opens the checked-in reference artifact for side-by-side review.
 */
function GoldenCorpusComparison() {
  const [lessonNumber, setLessonNumber] = useState(39)
  const [derivative, setDerivative] = useState<DerivativeKind>('pwa')
  const entry = corpus.find((candidate) => candidate.fixture.lessonNumber === lessonNumber)!
  const { fixture } = entry
  const panelId = `golden-${lessonNumber}-panel`
  const tabId = `golden-${lessonNumber}-${derivative}-tab`

  return (
    <main className="min-h-svh bg-background p-4 text-foreground sm:p-6">
      <div className="mx-auto max-w-6xl space-y-5">
        <header className="space-y-2">
          <p className="text-sm text-muted-foreground">Phase 2 · настоящий corpus</p>
          <h1 className="text-2xl font-semibold">Условия для начинающих: PWA · Telegram · PDF</h1>
          <p className="max-w-3xl text-sm text-muted-foreground">
            Все вкладки привязаны к исходным файлам уроков 39–41 и проверяются по SHA-256.
            Переключение не пересобирает и не редактирует математический материал.
          </p>
        </header>

        <div className="flex flex-wrap gap-2" aria-label="Выбор занятия">
          {corpus.map((candidate) => {
            const candidateLesson = candidate.fixture.lessonNumber
            return (
              <button
                aria-pressed={lessonNumber === candidateLesson}
                className="min-h-10 rounded-md border bg-card px-4 py-2 text-sm font-medium aria-pressed:border-primary aria-pressed:bg-accent"
                key={candidateLesson}
                onClick={() => setLessonNumber(candidateLesson)}
                type="button"
              >
                Занятие {candidateLesson}
              </button>
            )
          })}
        </div>

        <section className="break-all rounded-lg border bg-card p-4 text-xs text-muted-foreground">
          <p>{fixture.source.path}</p>
          <p>Source SHA-256: {fixture.source.sha256}</p>
          <p>Reference PDF SHA-256: {fixture.referencePdf.sha256}</p>
        </section>

        <div aria-label="Представление материала" className="flex flex-wrap gap-1" role="tablist">
          {(Object.keys(derivativeLabels) as DerivativeKind[]).map((kind) => (
            <button
              aria-controls={panelId}
              aria-selected={derivative === kind}
              className="min-h-10 rounded-md px-4 py-2 text-sm font-medium text-muted-foreground aria-selected:bg-accent aria-selected:text-foreground"
              id={`golden-${lessonNumber}-${kind}-tab`}
              key={kind}
              onClick={() => setDerivative(kind)}
              role="tab"
              type="button"
            >
              {derivativeLabels[kind]}
            </button>
          ))}
        </div>

        <section aria-labelledby={tabId} id={panelId} role="tabpanel">
          {derivative === 'pwa' ? (
            <SemanticMathDocument
              className="mx-auto max-w-3xl rounded-lg border bg-card p-5 sm:p-8"
              document={fixture.webDocument}
            />
          ) : derivative === 'telegram' ? (
            <TelegramDerivative fixture={fixture} />
          ) : (
            <div className="overflow-hidden rounded-lg border bg-card">
              <iframe
                className="h-[78svh] w-full"
                src={`${entry.pdfUrl}#view=FitH`}
                title={`PDF условий занятия ${fixture.lessonNumber} для начинающих`}
              />
            </div>
          )}
        </section>
      </div>
    </main>
  )
}

const meta = {
  title: 'Product/Mathematical document/Real corpus',
  component: GoldenCorpusComparison,
  parameters: { canvasPadding: false, layout: 'fullscreen' },
} satisfies Meta<typeof GoldenCorpusComparison>

export default meta
type Story = StoryObj<typeof meta>

export const BeginnerLessons39To41: Story = {
  name: 'Lessons 39–41 · PWA, Telegram and PDF',
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await waitFor(() => expect(canvasElement.querySelectorAll('.katex').length).toBeGreaterThan(2))
    await expect(canvas.getByText('Занятие 39 · Начинающие')).toBeVisible()

    await userEvent.click(canvas.getByRole('button', { name: 'Занятие 41' }))
    await expect(canvas.getByText('Занятие 41 · Начинающие')).toBeVisible()
    await userEvent.click(canvas.getByRole('tab', { name: 'Telegram Rich' }))
    await waitFor(() => expect(canvasElement.querySelectorAll('.katex').length).toBeGreaterThan(2))
    await expect(canvas.getByText('«Письменные» задачи')).toBeVisible()

    await userEvent.click(canvas.getByRole('tab', { name: 'PDF' }))
    const frame = canvas.getByTitle('PDF условий занятия 41 для начинающих')
    await expect(frame.getAttribute('src')).toContain('usl-41-n.pdf')
  },
}
