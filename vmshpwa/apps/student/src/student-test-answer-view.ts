import { testAnswerInputResponseSchema, type TestAnswerInputResponse } from '@vmsh/contracts'
import { answerTypeFromLegacyId, type AnswerSpec } from '@vmsh/product'

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
