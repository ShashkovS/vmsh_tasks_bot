import { ChevronDown, ChevronRight, MessageCircleQuestion, PencilLine } from 'lucide-react'
import { SemanticMathDocument, WorksheetDocument } from '@vmsh/content'
import type {
  WebContentBlock,
  WebContentDocument,
  WebContentProblem,
  WebFigureAvailableAsset,
} from '@vmsh/contracts'
import { WorksheetMaterials } from '@vmsh/product'
import { Badge, Button } from '@vmsh/ui'

function hasSubpart(blocks: WebContentBlock[]): boolean {
  return blocks.some(
    (block) =>
      block.type === 'subpart' ||
      (block.type === 'callout' && hasSubpart(block.blocks)) ||
      (block.type === 'list' && block.items.some(hasSubpart)),
  )
}
/** Same paper and disclosures as Student; no student mutations in this adapter. */
export function StaffWorksheetPreview({
  document,
  condition,
  hintDocument,
  solutionDocument,
  submissionClosed,
}: {
  document: WebContentDocument
  hintDocument?: WebContentDocument | undefined
  solutionDocument?: WebContentDocument | undefined
  condition: WebContentDocument | undefined
  submissionClosed: boolean
}) {
  const materialKind = document.materialKind
  const paper = materialKind === 'condition' ? document : condition
  if (!paper) return <p role="status">Для ученического превью сначала загрузите условия.</p>
  const actions = () => (
    <span className="vmsh-problem-actions-row font-sans">
      <Badge variant="neutral">Не начата</Badge>
      <Button disabled size="sm" variant="ghost">
        Открыть
        <ChevronRight aria-hidden="true" />
      </Button>
    </span>
  )
  const workspace = (problem: WebContentProblem, selectedPart?: string) => {
    const selectBlocks = (blocks: WebContentBlock[]): WebContentBlock[] =>
      blocks
        .flatMap((block): WebContentBlock[] => {
          if (block.type === 'subpart')
            return selectedPart === undefined
              ? [block]
              : block.label === selectedPart
                ? selectBlocks(block.blocks)
                : []
          if (block.type === 'callout') return [{ ...block, blocks: selectBlocks(block.blocks) }]
          if (block.type === 'list') return [{ ...block, items: block.items.map(selectBlocks) }]
          return [block]
        })
        .filter(
          (block, index, selected) =>
            !(
              block.type === 'heading' &&
              (index + 1 === selected.length || selected[index + 1]?.type === 'heading')
            ),
        )
    const material = (source: WebContentDocument | undefined) => {
      const matching = source?.problems.find((item) => item.ordinal === problem.ordinal)
      return source && matching ? (
        <SemanticMathDocument
          document={{
            ...source,
            title: null,
            introduction: [],
            problems: [{ ...matching, blocks: selectBlocks(matching.blocks) }],
          }}
          hideProblemHeadings
          imageLoading="eager"
        />
      ) : null
    }
    const hintContent = material(materialKind === 'hint' ? document : hintDocument)
    const solutionContent = material(materialKind === 'solution' ? document : solutionDocument)
    const hint = {
      available: hintContent !== null,
      preview: hintContent,
      load: () => Promise.resolve(hintContent),
    }
    const solution = {
      available: solutionContent !== null,
      preview: solutionContent,
      load: () => Promise.resolve(solutionContent),
    }
    return (
      <div className="mb-4">
        <div className="vmsh-problem-workspace mt-2 flex flex-wrap items-center gap-1.5 font-sans">
          {!submissionClosed ? (
            <Button disabled size="sm" variant="ghost">
              <PencilLine aria-hidden="true" className="size-4" />
              Ответить
              <ChevronDown aria-hidden="true" />
            </Button>
          ) : null}
          <Button disabled size="sm" variant="ghost">
            <MessageCircleQuestion aria-hidden="true" className="size-4" />
            Задать вопрос
          </Button>
          <WorksheetMaterials
            compact
            hint={hint}
            solution={solution}
            {...(materialKind !== 'condition' ? { defaultOpen: materialKind } : {})}
          />
        </div>
      </div>
    )
  }
  return (
    <>
      <p className="mb-3 text-small text-muted-foreground">
        Предпросмотр школьника. Отправка ответов, вопросы и переход к задаче отключены; просмотры не
        записываются.
      </p>
      <div
        data-density="student"
        className="mx-auto w-full max-w-5xl overflow-hidden rounded-lg border border-border bg-surface"
      >
        <WorksheetDocument
          document={paper}
          renderProblemActions={(problem) => (hasSubpart(problem.blocks) ? null : actions())}
          renderSubpartActions={actions}
          renderAfterProblem={(problem) => (hasSubpart(problem.blocks) ? null : workspace(problem))}
          renderAfterSubpart={workspace}
        />
      </div>
    </>
  )
}

export function FigureScaleTools({
  document,
  onScale,
}: {
  document: WebContentDocument
  onScale: (asset: WebFigureAvailableAsset, scale: number) => void
}) {
  const figures = new Map<string, { asset: WebFigureAvailableAsset; scale: number }>()
  const visit = (blocks: WebContentBlock[]) =>
    blocks.forEach((block) => {
      if (block.type === 'figure' && block.asset.status === 'available')
        figures.set(block.asset.assetId, { asset: block.asset, scale: block.scale ?? 1 })
      if (block.type === 'callout' || block.type === 'subpart') visit(block.blocks)
      if (block.type === 'list') block.items.forEach(visit)
    })
  visit(document.introduction)
  document.problems.forEach((problem) => {
    visit(problem.blocks)
    visit(problem.preambleBlocks ?? [])
    visit(problem.trailingBlocks ?? [])
  })
  if (!figures.size) return null
  return (
    <details className="mt-4">
      <summary className="cursor-pointer text-small">Масштаб рисунков для публикации</summary>
      <div className="mt-2 flex flex-wrap gap-3">
        {[...figures.values()].map(({ asset, scale }, index) => (
          <label key={asset.assetId} className="flex items-center gap-2 text-small">
            Рисунок {index + 1}
            <select
              className="rounded border border-border bg-surface p-2"
              value={scale}
              onChange={(event) => onScale(asset, Number(event.target.value))}
            >
              {[
                ...new Set([
                  0.25,
                  0.5,
                  0.6,
                  0.7,
                  0.8,
                  0.9,
                  1,
                  1.1,
                  1.2,
                  1.3,
                  1.4,
                  1.5,
                  1.75,
                  2,
                  2.5,
                  scale,
                ]),
              ]
                .sort((a, b) => a - b)
                .map((value) => (
                  <option key={value} value={value}>
                    {Math.round(value * 100)}%
                  </option>
                ))}
            </select>
          </label>
        ))}
      </div>
    </details>
  )
}
