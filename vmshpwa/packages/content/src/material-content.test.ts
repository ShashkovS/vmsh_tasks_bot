import { expect, it } from 'vitest'
import type { WebContentProblem } from '@vmsh/contracts'
import { materialProblemContent } from './material-content'

const problem: WebContentProblem = {
  ordinal: 1,
  sourceItem: '1',
  title: null,
  partLabels: ['а', 'б'],
  blocks: [
    { type: 'heading', level: 3, children: [{ type: 'text', value: 'Ответ' }] },
    {
      type: 'subpart',
      label: 'а',
      blocks: [{ type: 'paragraph', children: [{ type: 'text', value: '42' }] }],
    },
    {
      type: 'subpart',
      label: 'б',
      blocks: [{ type: 'paragraph', children: [{ type: 'text', value: '  ' }] }],
    },
  ],
}

it('selects a present independent part and rejects empty labels and orphan headings', () => {
  expect(materialProblemContent(problem, 'а')).toBeDefined()
  expect(materialProblemContent(problem, 'б')).toBeUndefined()
  expect(materialProblemContent(problem, 'в')).toBeUndefined()
})
it('uses source presence metadata for old derivatives containing condition illustrations', () => {
  expect(materialProblemContent({ ...problem, materialAvailable: false })).toBeUndefined()
  expect(materialProblemContent({ ...problem, materialPartLabels: ['а'] }, 'б')).toBeUndefined()
})
it('keeps shared material available for every part', () => {
  const common = {
    ...problem,
    blocks: [
      { type: 'paragraph' as const, children: [{ type: 'text' as const, value: 'Общий совет' }] },
    ],
  }
  expect(materialProblemContent(common, 'а')).toBeDefined()
  expect(materialProblemContent(common, 'б')).toBeDefined()
})
