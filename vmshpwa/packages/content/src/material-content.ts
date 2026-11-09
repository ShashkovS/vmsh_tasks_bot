import type { WebContentBlock, WebContentProblem } from '@vmsh/contracts'

function selectBlocks(blocks: WebContentBlock[], part?: string): WebContentBlock[] {
  return blocks
    .flatMap((block): WebContentBlock[] => {
      if (block.type === 'subpart')
        return part === undefined ? [block] : block.label === part ? selectBlocks(block.blocks) : []
      if (block.type === 'callout') return [{ ...block, blocks: selectBlocks(block.blocks, part) }]
      if (block.type === 'list')
        return [{ ...block, items: block.items.map((item) => selectBlocks(item, part)) }]
      return [block]
    })
    .filter(
      (block, index, selected) =>
        !(
          block.type === 'heading' &&
          (index + 1 === selected.length || selected[index + 1]?.type === 'heading')
        ),
    )
}

function hasBody(blocks: WebContentBlock[]): boolean {
  return blocks.some((block) => {
    if (block.type === 'heading') return false
    if (block.type === 'paragraph')
      return block.children.some((inline) =>
        inline.type === 'text' ? inline.value.trim().length > 0 : true,
      )
    if (block.type === 'callout' || block.type === 'subpart') return hasBody(block.blocks)
    if (block.type === 'list') return block.items.some(hasBody)
    return true
  })
}

/** Shared preview selection; docs/hint-preview-empty-materials-20261004.md. */
export function materialProblemContent(
  problem: WebContentProblem,
  part?: string,
): WebContentProblem | undefined {
  if (
    problem.materialAvailable === false ||
    (part !== undefined &&
      problem.materialPartLabels !== undefined &&
      !problem.materialPartLabels.includes(part))
  )
    return undefined
  const blocks = selectBlocks(problem.blocks, part)
  return hasBody(blocks) ? { ...problem, blocks } : undefined
}
