import { describe, expect, it } from 'vitest'

import { problemReviewDraftStorageKey } from './problem-review-draft'

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
