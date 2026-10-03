import { useState } from 'react'

/**
 * Reports a server replacement after the first publication has rendered.
 * Realtime only invalidates TanStack Query; the marker is derived from the
 * authoritative replacement response rather than from an ephemeral socket event.
 * See `dev/development-plan/06-phase-2-content.md` (published-content replacement).
 */
export function usePublishedContentReplacement(
  resourceKey: string | undefined,
  publicationId: string | undefined,
): boolean {
  const [observed, setObserved] = useState<{
    resourceKey: string | undefined
    publicationId: string | undefined
    wasReplaced: boolean
  }>({ resourceKey, publicationId, wasReplaced: false })

  if (observed.resourceKey !== resourceKey) {
    // React's guarded render-time adjustment makes the reset synchronous: a
    // mounted route never paints the previous resource's marker for one frame.
    setObserved({ resourceKey, publicationId, wasReplaced: false })
    return false
  }
  if (observed.publicationId !== publicationId) {
    const wasReplaced = observed.publicationId !== undefined && publicationId !== undefined
    setObserved({ resourceKey, publicationId, wasReplaced })
    return wasReplaced
  }

  return observed.wasReplaced
}
