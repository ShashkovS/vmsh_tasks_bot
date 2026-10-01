import { Trans } from '@lingui/react/macro'
import { ChevronDown, ChevronRight, MessageCircleQuestion, PencilLine } from 'lucide-react'
import { SemanticMathDocument, WorksheetDocument, type FigureToolsRenderer } from '@vmsh/content'
import type { WebContentBlock, WebContentDocument, WebContentProblem } from '@vmsh/contracts'
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
  renderFigureTools,
}: {
  document: WebContentDocument
  hintDocument?: WebContentDocument | undefined
  solutionDocument?: WebContentDocument | undefined
  condition: WebContentDocument | undefined
  submissionClosed: boolean
  renderFigureTools?: FigureToolsRenderer | undefined
}) {
  const materialKind = document.materialKind
  const paper = materialKind === 'condition' ? document : condition
  if (!paper)
    return (
      <p role="status">
        <Trans>Для ученического превью сначала загрузите условия.</Trans>
      </p>
    )
  const actions = () => (
    <span className="vmsh-problem-actions-row font-sans">
      <Badge variant="neutral">
        <Trans>Не начата</Trans>
      </Badge>
      <Button disabled size="sm" variant="ghost">
        <Trans>Открыть</Trans>
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
          renderFigureTools={source === document ? renderFigureTools : undefined}
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
              <Trans>Ответить</Trans>
              <ChevronDown aria-hidden="true" />
            </Button>
          ) : null}
          <Button disabled size="sm" variant="ghost">
            <MessageCircleQuestion aria-hidden="true" className="size-4" />
            <Trans>Задать вопрос</Trans>
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
        <Trans>
          Предпросмотр школьника. Отправка ответов, вопросы и переход к задаче отключены; просмотры
          не записываются.
        </Trans>
      </p>
      <div
        data-density="student"
        className="mx-auto w-full max-w-5xl overflow-hidden rounded-lg border border-border bg-surface"
      >
        <WorksheetDocument
          document={paper}
          renderFigureTools={materialKind === 'condition' ? renderFigureTools : undefined}
          renderProblemActions={(problem) => (hasSubpart(problem.blocks) ? null : actions())}
          renderSubpartActions={actions}
          renderAfterProblem={(problem) => (hasSubpart(problem.blocks) ? null : workspace(problem))}
          renderAfterSubpart={workspace}
        />
      </div>
    </>
  )
}
