import { z } from 'zod'

import { principalQueryKey, publicIdSchema, type PrincipalQueryScope } from './auth'
import { legacyVerdictIdSchema } from './courses'

/**
 * Phase-4 Student test-submission wire contract. The server is authoritative
 * for validation, cutoff and attempt limits; this schema deliberately exposes
 * neither configured answers nor checker source. See
 * `dev/development-plan/08-phase-4-test-submissions.md`.
 */

export const TEST_SUBMISSION_CONTRACT_VERSION = 1 as const
const testSubmissionContractVersionSchema = z.literal(TEST_SUBMISSION_CONTRACT_VERSION)

export const testProblemRevisionSchema = z
  .object({
    conditionRevisionId: publicIdSchema,
    configVersion: z.number().int().positive(),
  })
  .strict()
export type TestProblemRevision = z.infer<typeof testProblemRevisionSchema>

export const testAttemptOutcomeSchema = z.enum([
  'correct',
  'wrong',
  'invalid_format',
  'pending_configuration',
  'checker_failed',
])
export type TestAttemptOutcome = z.infer<typeof testAttemptOutcomeSchema>

export const testAttemptCheckStatusSchema = z.enum(['pending_configuration', 'checked', 'failed'])
export type TestAttemptCheckStatus = z.infer<typeof testAttemptCheckStatusSchema>

export const submitTestAnswerRequestSchema = z
  .object({
    schemaVersion: testSubmissionContractVersionSchema,
    idempotencyKey: z.uuid(),
    problemRevision: testProblemRevisionSchema,
    displayAnswer: z.string().max(16_384),
    clientCreatedAt: z.iso.datetime().regex(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/),
  })
  .strict()
export type SubmitTestAnswerRequest = z.infer<typeof submitTestAnswerRequestSchema>

export const testAttemptLimitReceiptSchema = z
  .object({
    usedThisHour: z.number().int().nonnegative(),
    remainingThisHour: z.number().int().nonnegative().nullable(),
    usedToday: z.number().int().nonnegative(),
    remainingToday: z.number().int().nonnegative().nullable(),
    unlimited: z.boolean(),
  })
  .strip()
  .superRefine((receipt, context) => {
    if (
      receipt.unlimited &&
      (receipt.remainingThisHour !== null || receipt.remainingToday !== null)
    ) {
      context.addIssue({
        code: 'custom',
        message: 'Unlimited attempt policy cannot expose a remaining limit',
        path: ['unlimited'],
      })
    }
  })
export type TestAttemptLimitReceipt = z.infer<typeof testAttemptLimitReceiptSchema>

const testAttemptCommonShape = {
  schemaVersion: testSubmissionContractVersionSchema,
  attemptId: publicIdSchema,
  problemId: publicIdSchema,
  problemRevision: testProblemRevisionSchema,
  outcome: testAttemptOutcomeSchema,
  checkStatus: testAttemptCheckStatusSchema,
  displayAnswer: z.string().max(16_384),
  feedback: z.string().max(16_384).nullable(),
  checkerMessage: z.string().max(16_384).nullable(),
  verdict: legacyVerdictIdSchema.nullable(),
  resultVersion: z.number().int().positive().nullable(),
  clientCreatedAt: z.iso.datetime(),
  serverReceivedAt: z.iso.datetime(),
  clockSuspicious: z.boolean(),
  threadInvalidationKey: z.string().min(1).max(256),
}

function refineAttemptState(
  attempt: {
    problemId: string
    outcome: TestAttemptOutcome
    checkStatus: TestAttemptCheckStatus
    verdict: number | null
    resultVersion: number | null
    threadInvalidationKey: string
  },
  context: z.RefinementCtx,
): void {
  const expectedCheckStatus = {
    correct: 'checked',
    wrong: 'checked',
    invalid_format: 'checked',
    pending_configuration: 'pending_configuration',
    checker_failed: 'failed',
  } as const satisfies Record<TestAttemptOutcome, TestAttemptCheckStatus>
  const resolvedCheckStatus = expectedCheckStatus[attempt.outcome]
  if (attempt.checkStatus !== resolvedCheckStatus) {
    context.addIssue({
      code: 'custom',
      message: 'Attempt check status must match its outcome',
      path: ['checkStatus'],
    })
  }

  const expectedVerdict =
    attempt.outcome === 'correct' ? 18 : attempt.outcome === 'wrong' ? -1 : null
  if (attempt.verdict !== expectedVerdict) {
    context.addIssue({
      code: 'custom',
      message: 'Attempt verdict must match its outcome',
      path: ['verdict'],
    })
  }
  if ((attempt.resultVersion === null) !== (attempt.verdict === null)) {
    context.addIssue({
      code: 'custom',
      message: 'Only a persisted verdict may expose a result version',
      path: ['resultVersion'],
    })
  }

  const expectedInvalidationKey = `problems/${attempt.problemId}/test-attempts`
  if (attempt.threadInvalidationKey !== expectedInvalidationKey) {
    context.addIssue({
      code: 'custom',
      message: 'Attempt invalidation key must be scoped to its problem',
      path: ['threadInvalidationKey'],
    })
  }
}

export const testAttemptHistoryItemSchema = z
  .object(testAttemptCommonShape)
  .strip()
  .superRefine(refineAttemptState)
export type TestAttemptHistoryItem = z.infer<typeof testAttemptHistoryItemSchema>

export const submitTestAnswerResponseSchema = z
  .object({
    ...testAttemptCommonShape,
    attempts: testAttemptLimitReceiptSchema,
    requestId: z.string().trim().min(1).max(200),
  })
  .strip()
  .superRefine(refineAttemptState)
export type SubmitTestAnswerResponse = z.infer<typeof submitTestAnswerResponseSchema>

export const testAttemptCursorSchema = publicIdSchema.brand<'TestAttemptCursor'>()
export type TestAttemptCursor = z.infer<typeof testAttemptCursorSchema>

export const testAttemptHistoryResponseSchema = z
  .object({
    problemId: publicIdSchema,
    attempts: z.array(testAttemptHistoryItemSchema).max(50),
    nextCursor: testAttemptCursorSchema.nullable(),
    requestId: z.string().trim().min(1).max(200),
  })
  .strip()
  .superRefine((response, context) => {
    const seen = new Set<string>()
    let previousTimestamp: string | null = null
    response.attempts.forEach((attempt, index) => {
      if (attempt.problemId !== response.problemId) {
        context.addIssue({
          code: 'custom',
          message: 'Every attempt must belong to the requested problem',
          path: ['attempts', index, 'problemId'],
        })
      }
      if (seen.has(attempt.attemptId)) {
        context.addIssue({
          code: 'custom',
          message: 'Attempt IDs must be unique within a history page',
          path: ['attempts', index, 'attemptId'],
        })
      }
      if (previousTimestamp !== null && attempt.serverReceivedAt > previousTimestamp) {
        context.addIssue({
          code: 'custom',
          message: 'Attempt history must use reverse chronological order',
          path: ['attempts', index, 'serverReceivedAt'],
        })
      }
      seen.add(attempt.attemptId)
      previousTimestamp = attempt.serverReceivedAt
    })
  })
export type TestAttemptHistoryResponse = z.infer<typeof testAttemptHistoryResponseSchema>

export const testSubmissionQueryKeys = {
  all: (principal: PrincipalQueryScope) =>
    [...principalQueryKey(principal), 'test-attempts'] as const,
  problem: (principal: PrincipalQueryScope, problemId: string) =>
    [...testSubmissionQueryKeys.all(principal), publicIdSchema.parse(problemId)] as const,
  history: (principal: PrincipalQueryScope, problemId: string, cursor: string | null = null) =>
    [
      ...testSubmissionQueryKeys.problem(principal, problemId),
      'history',
      cursor === null ? 'first' : testAttemptCursorSchema.parse(cursor),
    ] as const,
} as const

export const testSubmissionMutationFixtureSchema = z
  .object({
    fixtureVersion: testSubmissionContractVersionSchema,
    request: submitTestAnswerRequestSchema,
    response: submitTestAnswerResponseSchema,
  })
  .strict()

export const testSubmissionHistoryFixtureSchema = z
  .object({
    fixtureVersion: testSubmissionContractVersionSchema,
    response: testAttemptHistoryResponseSchema,
  })
  .strict()
