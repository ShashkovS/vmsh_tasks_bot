import type { SupportThreadSummary } from '@vmsh/contracts'

export function supportProblemLabel(context: SupportThreadSummary['context']) {
  return (
    [context.problemNumber, context.problemTitle].filter(Boolean).join(' · ') ||
    'Общий вопрос по занятию'
  )
}
