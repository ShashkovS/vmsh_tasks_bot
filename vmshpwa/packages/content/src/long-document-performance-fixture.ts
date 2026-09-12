import lesson39Fixture from '@vmsh/contracts/fixtures/content/golden/lesson-39-n.v1.json'
import lesson40Fixture from '@vmsh/contracts/fixtures/content/golden/lesson-40-n.v1.json'
import lesson41Fixture from '@vmsh/contracts/fixtures/content/golden/lesson-41-n.v1.json'
import {
  goldenContentComparisonFixtureSchema,
  webContentDocumentSchema,
  type WebContentBlock,
  type WebContentDocument,
  type WebInlineNode,
} from '@vmsh/contracts'

const corpus = [lesson39Fixture, lesson40Fixture, lesson41Fixture].map((fixture) =>
  goldenContentComparisonFixtureSchema.parse(fixture),
)

/**
 * A deliberately oversized browser fixture composed only from the checked-in
 * lesson 39–41 golden corpus. Four copies are large enough to catch accidental
 * quadratic rendering without pretending that wall-clock timing is a product SLO.
 */
export const longDocumentPerformanceFixtureCycles = 4
export const longDocumentRenderBudgetMs = 2_500

function countInlineMath(nodes: WebInlineNode[]): number {
  return nodes.reduce((count, node) => {
    if (node.type === 'math') return count + 1
    if (node.type === 'strong' || node.type === 'emphasis' || node.type === 'link') {
      return count + countInlineMath(node.children)
    }
    return count
  }, 0)
}

function countBlockMath(blocks: WebContentBlock[]): number {
  return blocks.reduce((count, block) => {
    switch (block.type) {
      case 'paragraph':
      case 'heading':
        return count + countInlineMath(block.children)
      case 'formula':
        return count + 1
      case 'list':
        return count + block.items.reduce((sum, item) => sum + countBlockMath(item), 0)
      case 'table':
        return (
          count +
          (block.caption ? countInlineMath(block.caption) : 0) +
          block.rows.reduce(
            (rowSum, row) =>
              rowSum + row.reduce((cellSum, cell) => cellSum + countInlineMath(cell.children), 0),
            0,
          )
        )
      case 'figure':
        return count + (block.caption ? countInlineMath(block.caption) : 0)
      case 'subpart':
        return count + countBlockMath(block.blocks)
      case 'callout':
        return count + countBlockMath(block.blocks)
      case 'divider':
        return count
    }
  }, 0)
}

export function countDocumentMathExpressions(document: WebContentDocument): number {
  return (
    countBlockMath(document.introduction) +
    document.problems.reduce(
      (count, problem) =>
        count +
        countBlockMath(problem.preambleBlocks ?? []) +
        countBlockMath(problem.blocks) +
        countBlockMath(problem.trailingBlocks ?? []),
      0,
    )
  )
}

export function buildLongRealCorpusDocument(): WebContentDocument {
  let ordinal = 0
  const problems = Array.from({ length: longDocumentPerformanceFixtureCycles }, (_, cycleIndex) =>
    corpus.flatMap((entry) =>
      entry.webDocument.problems.map((problem) => {
        ordinal += 1
        // The contract rejects repeated object references as potentially cyclic;
        // each stress copy must therefore remain a genuine JSON tree.
        const blocks: WebContentBlock[] = structuredClone(problem.blocks)
        const trailingBlocks: WebContentBlock[] = structuredClone(problem.trailingBlocks ?? [])
        if (ordinal === 1) {
          blocks.push({
            type: 'figure',
            alt: 'Недоступный SVG в проверке длинного листка',
            caption: [{ type: 'text', value: 'Подпись сохраняется при ошибке загрузки SVG.' }],
            asset: {
              status: 'available',
              assetId: 'asset:long-sheet-missing-svg',
              contentSha256: '2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae',
              src: '/content/long-sheet-missing.svg',
              mediaType: 'image/svg+xml',
              width: 800,
              height: 480,
            },
          })
        }
        return {
          ...problem,
          ordinal,
          sourceItem: `${entry.lessonNumber}н.${problem.ordinal} · проход ${cycleIndex + 1}`,
          blocks,
          trailingBlocks,
        }
      }),
    ),
  ).flat()

  return webContentDocumentSchema.parse({
    contractVersion: 1,
    revisionId: 'revision:golden-lessons-39-41-long-render-probe',
    sourceSha256: 'ea05ba31c0d425819088d50998d85ba35fc5b4deb233dc5ef553fb57c391bf82',
    materialKind: 'condition',
    title: 'Stress-проверка реального corpus · занятия 39–41',
    introduction: [
      {
        type: 'paragraph',
        children: [
          {
            type: 'text',
            value:
              'Проверочный документ повторяет неизменённые задачи золотого корпуса, чтобы измерение было воспроизводимым.',
          },
        ],
      },
    ],
    problems,
  })
}

export const longRealCorpusDocument = buildLongRealCorpusDocument()
export const longRealCorpusExpectedProblemCount = longRealCorpusDocument.problems.length
export const longRealCorpusExpectedMathCount = countDocumentMathExpressions(longRealCorpusDocument)
