import {
  testAnswerInputResponseSchema,
  type TestAnswerInputResponse,
  type TestAttemptOutcome,
} from '@vmsh/contracts'
import {
  answerTypeFromLegacyId,
  binaryVerdictScale,
  findVerdict,
  type AnswerSpec,
  type VerdictView,
} from '@vmsh/product'

/** Safe API input configuration translated to the shared historical control. */
export function testAnswerSpec(input: TestAnswerInputResponse): AnswerSpec {
  const parsed = testAnswerInputResponseSchema.parse(input)
  return {
    type: answerTypeFromLegacyId(parsed.answerType),
    ...(parsed.validationPattern === null ? {} : { validationPattern: parsed.validationPattern }),
    ...(parsed.validationError === null ? {} : { validationError: parsed.validationError }),
    ...(parsed.options.length === 0
      ? {}
      : {
          options: parsed.options.map((option) => ({ value: option, label: option })),
        }),
  }
}

/*
 * An automatically checked answer reads as a short exchange with the bot: the
 * student sends an answer, the checker answers back. The wording below is the
 * bot's reply; the per-attempt detail from the checker follows it.
 */
const replyByOutcome: Record<TestAttemptOutcome, string> = {
  correct: 'Да, ответ принят.',
  wrong: 'Ответ пока неверный.',
  invalid_format: 'Проверьте формат ответа.',
  pending_configuration: 'Ответ сохранён и ждёт настройки проверки.',
  checker_failed: 'Ответ сохранён, но проверка не завершилась.',
}

export function testAttemptReply(attempt: {
  outcome: TestAttemptOutcome
  feedback: string | null
  checkerMessage: string | null
}): string {
  // The checker's own wording is the reply when it has one; the verdict mark
  // beside it already states the outcome, so the canned line would only repeat.
  const detail = attempt.feedback?.trim() || attempt.checkerMessage?.trim() || ''
  return detail || replyByOutcome[attempt.outcome]
}

/** Automatic checking is binary; anything unresolved carries no verdict yet. */
export function testAttemptVerdict(outcome: TestAttemptOutcome): VerdictView | undefined {
  if (outcome === 'correct') return findVerdict(binaryVerdictScale, 'plus')
  if (outcome === 'wrong') return findVerdict(binaryVerdictScale, 'rejected')
  return undefined
}
