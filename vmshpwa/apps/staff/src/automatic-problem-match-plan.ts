import type { ProblemMatchMutationRow, ProblemMatchReview } from '@vmsh/contracts'

function problemKey(sourceOrdinal: number, sourceItem: string): string {
  return JSON.stringify([sourceOrdinal, sourceItem])
}

function normalizedItem(value: string): string {
  return value.normalize('NFKC').trim().toLocaleLowerCase('ru-RU')
}

/** Resolve the ordinary revision update without asking for a row-by-row map. */
export function automaticProblemMatchPlan(
  review: ProblemMatchReview,
  allowInsert: boolean,
): ProblemMatchMutationRow[] | undefined {
  if (review.candidates.length === 0) {
    return allowInsert
      ? review.items.map((item) => ({
          sourceOrdinal: item.sourceOrdinal,
          sourceItem: item.sourceItem,
          decision: 'insert_new' as const,
          problemId: null,
        }))
      : undefined
  }

  const decisions = new Map<string, ProblemMatchMutationRow>()
  const usedCandidates = new Set<number>()
  for (const item of review.items) {
    if (!item.match) continue
    decisions.set(problemKey(item.sourceOrdinal, item.sourceItem), {
      sourceOrdinal: item.sourceOrdinal,
      sourceItem: item.sourceItem,
      decision: item.match.problemId === null ? 'omit' : 'auto_position',
      problemId: item.match.problemId,
    })
    if (item.match.problemId !== null) usedCandidates.add(item.match.problemId)
  }

  const ordinals = [...new Set(review.items.map((item) => item.sourceOrdinal))].sort(
    (left, right) => left - right,
  )
  for (const ordinal of ordinals) {
    const items = review.items.filter(
      (item) =>
        item.sourceOrdinal === ordinal && !decisions.has(problemKey(ordinal, item.sourceItem)),
    )
    const candidates = review.candidates.filter(
      (candidate) =>
        candidate.problemNumber === ordinal && !usedCandidates.has(candidate.problemId),
    )

    for (const item of items) {
      const matches = candidates.filter(
        (candidate) =>
          !usedCandidates.has(candidate.problemId) &&
          normalizedItem(candidate.item) === normalizedItem(item.sourceItem),
      )
      if (matches.length !== 1) continue
      const candidate = matches[0]!
      usedCandidates.add(candidate.problemId)
      decisions.set(problemKey(ordinal, item.sourceItem), {
        sourceOrdinal: ordinal,
        sourceItem: item.sourceItem,
        decision: 'auto_position',
        problemId: candidate.problemId,
      })
    }

    const remainingItems = items.filter(
      (item) => !decisions.has(problemKey(ordinal, item.sourceItem)),
    )
    const remainingCandidates = candidates.filter(
      (candidate) => !usedCandidates.has(candidate.problemId),
    )
    if (remainingCandidates.length > remainingItems.length) return undefined

    remainingCandidates.forEach((candidate, index) => {
      const item = remainingItems[index]!
      usedCandidates.add(candidate.problemId)
      decisions.set(problemKey(ordinal, item.sourceItem), {
        sourceOrdinal: ordinal,
        sourceItem: item.sourceItem,
        decision: 'auto_position',
        problemId: candidate.problemId,
      })
    })
    for (const item of remainingItems.slice(remainingCandidates.length)) {
      if (!allowInsert) return undefined
      decisions.set(problemKey(ordinal, item.sourceItem), {
        sourceOrdinal: ordinal,
        sourceItem: item.sourceItem,
        decision: 'insert_new',
        problemId: null,
      })
    }
  }

  if (review.candidates.some((candidate) => !usedCandidates.has(candidate.problemId))) {
    return undefined
  }
  const plan = review.items.map((item) =>
    decisions.get(problemKey(item.sourceOrdinal, item.sourceItem)),
  )
  return plan.every((item): item is ProblemMatchMutationRow => item !== undefined)
    ? plan
    : undefined
}
