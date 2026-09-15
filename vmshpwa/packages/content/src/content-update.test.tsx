import { renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { usePublishedContentReplacement } from './content-update'

describe('published-content replacement marker', () => {
  it('resets across resources and marks only a replacement of the same resource', () => {
    const { result, rerender } = renderHook(
      ({ resourceKey, revisionId }: { resourceKey: string; revisionId: string | undefined }) =>
        usePublishedContentReplacement(resourceKey, revisionId),
      {
        initialProps: {
          resourceKey: 'student:lesson-41:condition',
          revisionId: undefined as string | undefined,
        },
      },
    )

    rerender({ resourceKey: 'student:lesson-41:condition', revisionId: 'revision-condition-1' })
    expect(result.current).toBe(false)

    rerender({ resourceKey: 'student:lesson-41:condition', revisionId: 'revision-condition-2' })
    expect(result.current).toBe(true)

    rerender({ resourceKey: 'student:lesson-42:condition', revisionId: 'revision-condition-7' })
    expect(result.current).toBe(false)

    rerender({ resourceKey: 'student:lesson-42:condition', revisionId: 'revision-condition-8' })
    expect(result.current).toBe(true)
  })
})
