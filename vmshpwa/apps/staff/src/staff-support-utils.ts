import { t } from '@lingui/core/macro'
import type { SupportThreadSummary } from '@vmsh/contracts'

export function supportProblemLabel(context: SupportThreadSummary['context']) {
  return (
    [context.problemNumber, context.problemTitle].filter(Boolean).join(' · ') ||
    t`Общий вопрос по занятию`
  )
}
