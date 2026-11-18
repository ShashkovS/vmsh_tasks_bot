import type { ReactNode } from 'react'
import type { StudentProblemSummary, WebContentBlock, WebContentProblem } from '@vmsh/contracts'

function containsSubpart(blocks: WebContentBlock[]): boolean {
  return blocks.some((block) => {
    if (block.type === 'subpart') return true
    if (block.type === 'callout') return containsSubpart(block.blocks)
    if (block.type === 'list') return block.items.some(containsSubpart)
    return false
  })
}

function subpartProblem(
  problems: StudentProblemSummary[],
  documentProblem: WebContentProblem,
  label: string,
): StudentProblemSummary | undefined {
  return problems.find(
    (problem) =>
      problem.sourceOrdinal === documentProblem.ordinal && problem.displayNumber.endsWith(label),
  )
}

/** Shared feed/detail placement; see dev/design-system/05-pages-and-flows.md. */
export function studentWorksheetBindings(
  problems: StudentProblemSummary[],
  problemWorkspace: (problem: StudentProblemSummary) => ReactNode,
  problemActions: (problem: StudentProblemSummary) => ReactNode,
) {
  const problemsFor = (documentProblem: WebContentProblem) =>
    problems.filter((problem) => problem.sourceOrdinal === documentProblem.ordinal)
  return {
    renderAfterSubpart: (documentProblem: WebContentProblem, label: string) => {
      const problem = subpartProblem(problems, documentProblem, label)
      return problem ? <div className="mb-4">{problemWorkspace(problem)}</div> : null
    },
    renderAfterProblem: (documentProblem: WebContentProblem) => {
      if (containsSubpart(documentProblem.blocks)) return null
      const problems = problemsFor(documentProblem)
      if (problems.length === 0) return null
      return (
        <div className="mb-4 space-y-2">
          {problems.map((problem) => (
            <div key={problem.problemId}>{problemWorkspace(problem)}</div>
          ))}
        </div>
      )
    },
    renderProblemActions: (documentProblem: WebContentProblem) => {
      if (containsSubpart(documentProblem.blocks)) return null
      const problems = problemsFor(documentProblem)
      return problems.length === 1 && problems[0] ? problemActions(problems[0]) : null
    },
    renderSubpartActions: (documentProblem: WebContentProblem, label: string) => {
      const problem = subpartProblem(problems, documentProblem, label)
      return problem ? problemActions(problem) : null
    },
  }
}
