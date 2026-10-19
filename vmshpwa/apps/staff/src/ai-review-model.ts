import type { AiReviewSuggestion, ReviewWorkspaceEvidence } from '@vmsh/contracts'
import type { ReviewFeedbackDraft } from '@vmsh/product'

// Snapshot matching and independent application; docs/ai-review-assistant.md.
const wireValues = ['rejected', 'minus-dot', 'minus-plus', 'half', 'plus-minus', 'plus-dot', 'plus']

export function aiEvidenceKey(workspace: ReviewWorkspaceEvidence) {
  return workspace.evidenceBranches
    .flatMap((branch) =>
      branch.thread
        ? [
            `${branch.thread.threadId}@${branch.thread.threadVersion}:${branch.thread.entries.map((entry) => `${entry.entryId}@${entry.entryVersion}`).join(',')}`,
          ]
        : [],
    )
    .sort()
    .join('|')
}

export function applyAiSuggestion(
  draft: ReviewFeedbackDraft,
  suggestion: AiReviewSuggestion,
  field: 'comment' | 'verdict',
): ReviewFeedbackDraft {
  if (field === 'comment' && suggestion.comment) {
    return { ...draft, comment: [draft.comment, suggestion.comment].filter(Boolean).join('\n\n') }
  }
  return field === 'verdict' && suggestion.verdict !== null
    ? { ...draft, verdictValue: wireValues[suggestion.verdict - 11] ?? draft.verdictValue }
    : draft
}
