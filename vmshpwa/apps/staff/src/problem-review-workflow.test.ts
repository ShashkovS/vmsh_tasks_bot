import { describe, expect, it } from 'vitest'

import type { ProblemMatchReview } from '@vmsh/contracts'

import { automaticProblemMatchPlan } from './automatic-problem-match-plan'
import { problemReviewDraftStorageKey } from './problem-review-draft'

function review(
  items: Array<[number, string]>,
  candidates: Array<[number, number, string]>,
): ProblemMatchReview {
  return {
    revisionId: 'content-revision-test',
    groupLessonId: 'group-lesson-test',
    version: 1,
    etag: '"content-revision-test:v1"' as ProblemMatchReview['etag'],
    requestId: 'test-request',
    items: items.map(([sourceOrdinal, sourceItem]) => ({
      sourceOrdinal,
      sourceItem,
      displayNumber: `${sourceOrdinal}${sourceItem}`,
      sourceTitle: null,
      suggestedProblemId: null,
      match: null,
    })),
    candidates: candidates.map(([problemId, problemNumber, item]) => ({
      problemId,
      problemNumber,
      item,
      title: '',
      problemType: 2,
      answerType: null,
      answerValidation: null,
      validationError: null,
      correctAnswer: null,
      correctAnswerChecker: null,
      wrongAnswer: null,
      congratulation: null,
    })),
  }
}

describe('problem review draft namespace', () => {
  it('isolates one entity revision by runtime and Staff account', () => {
    const first = problemReviewDraftStorageKey(
      'agent:account-teacher-a',
      'metadata',
      'group-lesson-41',
      'revision-2',
    )
    const second = problemReviewDraftStorageKey(
      'agent:account-teacher-b',
      'metadata',
      'group-lesson-41',
      'revision-2',
    )

    expect(first).not.toBe(second)
    expect(first).toBe(
      'vmshpwa:staff:content:agent:account-teacher-a:metadata:v1:group-lesson-41:revision-2',
    )
  })

  it('keeps matching, metadata and base revisions independent', () => {
    const metadata = problemReviewDraftStorageKey(
      'agent:account-teacher-a',
      'metadata',
      'group-lesson-41',
      'revision-2',
    )

    expect(
      problemReviewDraftStorageKey(
        'agent:account-teacher-a',
        'matching',
        'group-lesson-41',
        'revision-2',
      ),
    ).not.toBe(metadata)
    expect(
      problemReviewDraftStorageKey(
        'agent:account-teacher-a',
        'metadata',
        'group-lesson-41',
        'revision-3',
      ),
    ).not.toBe(metadata)
  })
})

describe('automatic problem matching', () => {
  it('reuses an old unsplit task for the first point and inserts the additional point', () => {
    expect(
      automaticProblemMatchPlan(
        review(
          [
            [1, ''],
            [2, ''],
            [3, 'а'],
            [3, 'б'],
          ],
          [
            [101, 1, ''],
            [102, 2, ''],
            [103, 3, ''],
          ],
        ),
        true,
      ),
    ).toEqual([
      { sourceOrdinal: 1, sourceItem: '', decision: 'auto_position', problemId: 101 },
      { sourceOrdinal: 2, sourceItem: '', decision: 'auto_position', problemId: 102 },
      { sourceOrdinal: 3, sourceItem: 'а', decision: 'auto_position', problemId: 103 },
      { sourceOrdinal: 3, sourceItem: 'б', decision: 'insert_new', problemId: null },
    ])
  })

  it('does not silently drop an old task when the new source has fewer rows', () => {
    expect(
      automaticProblemMatchPlan(
        review(
          [[1, '']],
          [
            [101, 1, ''],
            [102, 2, ''],
          ],
        ),
        true,
      ),
    ).toBeUndefined()
  })

  it('requires an explicit choice when a named source task is renamed', () => {
    expect(
      automaticProblemMatchPlan(
        review(
          [[1, 'новая-метка']],
          [[101, 1, 'старая-метка']],
        ),
        true,
      ),
    ).toBeUndefined()
  })
})
