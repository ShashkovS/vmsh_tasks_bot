import { describe, expect, it } from 'vitest'

import historyFixture from '../fixtures/submissions/history.v1.json'
import inputFixture from '../fixtures/submissions/input.v1.json'
import mutationFixture from '../fixtures/submissions/mutation.v1.json'
import recheckFixture from '../fixtures/submissions/recheck.v1.json'

import {
  submitTestAnswerRequestSchema,
  submitTestAnswerResponseSchema,
  testAnswerInputResponseSchema,
  testAttemptHistoryResponseSchema,
  testSubmissionHistoryFixtureSchema,
  testSubmissionMutationFixtureSchema,
  testSubmissionQueryKeys,
  testSubmissionRecheckFixtureSchema,
  testAttemptRecheckResponseSchema,
} from './submissions'

describe('Phase-4 test-submission contracts', () => {
  it('keeps the versioned mutation fixture in parity with the strict wire contract', () => {
    expect(testSubmissionMutationFixtureSchema.parse(mutationFixture)).toEqual(mutationFixture)
  })

  it('keeps the versioned history fixture ordered and owner-resource scoped', () => {
    expect(testSubmissionHistoryFixtureSchema.parse(historyFixture)).toEqual(historyFixture)
  })

  it('keeps the Staff recheck fixture revision-bound and internally consistent', () => {
    expect(testSubmissionRecheckFixtureSchema.parse(recheckFixture)).toEqual(recheckFixture)
    expect(
      testAttemptRecheckResponseSchema.safeParse({
        ...recheckFixture.response,
        checked: 3,
      }).success,
    ).toBe(false)
    expect(
      testAttemptRecheckResponseSchema.safeParse({
        ...recheckFixture.response,
        threadInvalidationKey: 'problems/another/test-attempts',
      }).success,
    ).toBe(false)
  })

  it('exposes input help and visible choices without checker secrets', () => {
    expect(testAnswerInputResponseSchema.parse(inputFixture.response)).toEqual(
      inputFixture.response,
    )
    expect(JSON.stringify(inputFixture.response)).not.toMatch(/correctAnswer|checker/i)
    expect(
      testAnswerInputResponseSchema.safeParse({
        ...inputFixture.response,
        validationPattern: 'Чётное;Нечётное',
      }).success,
    ).toBe(false)
    expect(
      testAnswerInputResponseSchema.safeParse({
        ...inputFixture.response,
        answerType: 2,
      }).success,
    ).toBe(false)
  })

  it('rejects request extras, invalid UUIDs and non-UTC client timestamps', () => {
    expect(
      submitTestAnswerRequestSchema.safeParse({
        ...mutationFixture.request,
        studentId: 'user-must-not-be-client-controlled',
      }).success,
    ).toBe(false)
    expect(
      submitTestAnswerRequestSchema.safeParse({
        ...mutationFixture.request,
        idempotencyKey: 'not-a-uuid',
      }).success,
    ).toBe(false)
    expect(
      submitTestAnswerRequestSchema.safeParse({
        ...mutationFixture.request,
        clientCreatedAt: '2026-09-20T16:00:00',
      }).success,
    ).toBe(false)
    const withoutRevision: Record<string, unknown> = { ...mutationFixture.request }
    delete withoutRevision.problemRevision
    expect(submitTestAnswerRequestSchema.safeParse(withoutRevision).success).toBe(false)
    expect(
      submitTestAnswerRequestSchema.safeParse({
        ...mutationFixture.request,
        problemRevision: {
          ...mutationFixture.request.problemRevision,
          configVersion: true,
        },
      }).success,
    ).toBe(false)
  })

  it.each([
    { outcome: 'correct', checkStatus: 'failed' },
    { outcome: 'wrong', verdict: 18 },
    { outcome: 'invalid_format', resultVersion: 1 },
    { threadInvalidationKey: 'problems/another-problem/test-attempts' },
  ])('rejects an internally inconsistent mutation %#', (change) => {
    expect(
      submitTestAnswerResponseSchema.safeParse({
        ...mutationFixture.response,
        ...change,
      }).success,
    ).toBe(false)
  })

  it('rejects cross-problem, duplicate and forward-ordered history rows', () => {
    const response = historyFixture.response
    const first = response.attempts[0]
    const second = response.attempts[1]
    if (!first || !second) throw new Error('Expected two attempt fixtures')

    expect(
      testAttemptHistoryResponseSchema.safeParse({
        ...response,
        attempts: [{ ...first, problemId: 'problem-another' }],
      }).success,
    ).toBe(false)
    expect(
      testAttemptHistoryResponseSchema.safeParse({
        ...response,
        attempts: [first, { ...second, attemptId: first.attemptId }],
      }).success,
    ).toBe(false)
    expect(
      testAttemptHistoryResponseSchema.safeParse({
        ...response,
        attempts: [second, first],
      }).success,
    ).toBe(false)
  })

  it('keys history by principal, problem and cursor without leaking between accounts', () => {
    const firstPrincipal = { audience: 'student' as const, accountId: 'account-first' }
    const secondPrincipal = { audience: 'student' as const, accountId: 'account-second' }
    const first = testSubmissionQueryKeys.history(firstPrincipal, 'problem-fixture-test')
    const next = testSubmissionQueryKeys.history(
      firstPrincipal,
      'problem-fixture-test',
      'attempt-fixture-wrong',
    )

    expect(first).not.toEqual(next)
    expect(first).not.toEqual(
      testSubmissionQueryKeys.history(secondPrincipal, 'problem-fixture-test'),
    )
    expect(() => testSubmissionQueryKeys.history(firstPrincipal, '../unsafe-problem')).toThrow()
    const staffPrincipal = { audience: 'staff' as const, accountId: 'account-staff' }
    expect(testSubmissionQueryKeys.recheck(staffPrincipal, 'problem-fixture-test')).toEqual([
      ...testSubmissionQueryKeys.problem(staffPrincipal, 'problem-fixture-test'),
      'recheck',
    ])
  })
})
