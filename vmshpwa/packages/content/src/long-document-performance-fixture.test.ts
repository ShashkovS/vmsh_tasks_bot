import { describe, expect, it } from 'vitest'

import {
  countDocumentMathExpressions,
  longDocumentPerformanceFixtureCycles,
  longRealCorpusDocument,
  longRealCorpusExpectedMathCount,
  longRealCorpusExpectedProblemCount,
} from './long-document-performance-fixture'

describe('long real-corpus document fixture', () => {
  it('keeps the stress workload tied to four copies of lessons 39–41', () => {
    expect(longDocumentPerformanceFixtureCycles).toBe(4)
    expect(longRealCorpusExpectedProblemCount).toBe(132)
    expect(longRealCorpusExpectedMathCount).toBe(56)
    expect(countDocumentMathExpressions(longRealCorpusDocument)).toBe(56)
    expect(longRealCorpusDocument.problems.at(0)?.sourceItem).toBe('39н.1 · проход 1')
    expect(longRealCorpusDocument.problems.at(-1)?.sourceItem).toBe('41н.11 · проход 4')
  })

  it('contains one load-error SVG without changing the source problems', () => {
    const figures = longRealCorpusDocument.problems.flatMap((problem) =>
      problem.blocks.filter((block) => block.type === 'figure'),
    )

    expect(figures).toHaveLength(1)
    expect(figures[0]).toMatchObject({
      alt: 'Недоступный SVG в проверке длинного листка',
      asset: { status: 'available', src: '/content/long-sheet-missing.svg' },
    })
  })
})
