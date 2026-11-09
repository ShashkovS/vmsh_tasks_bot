import { renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { usePublishedContentReplacement } from './content-update'

describe('published-content replacement marker', () => {
  it('resets across resources and marks only a replacement of the same resource', () => {
    const { result, rerender } = renderHook(
      ({
        resourceKey,
        publicationId,
      }: {
        resourceKey: string
        publicationId: string | undefined
      }) => usePublishedContentReplacement(resourceKey, publicationId),
      {
        initialProps: {
          resourceKey: 'student:lesson-41:condition',
          publicationId: undefined as string | undefined,
        },
      },
    )

    rerender({
      resourceKey: 'student:lesson-41:condition',
      publicationId: 'publication-condition-1',
    })
    expect(result.current).toBe(false)

    rerender({
      resourceKey: 'student:lesson-41:condition',
      publicationId: 'publication-condition-2',
    })
    expect(result.current).toBe(true)

    rerender({
      resourceKey: 'student:lesson-42:condition',
      publicationId: 'publication-condition-7',
    })
    expect(result.current).toBe(false)

    rerender({
      resourceKey: 'student:lesson-42:condition',
      publicationId: 'publication-condition-8',
    })
    expect(result.current).toBe(true)
  })
})
