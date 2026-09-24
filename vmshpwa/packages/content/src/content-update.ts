import { useState } from 'react'

/**
 * Reports a server replacement after the first published revision has rendered.
 * Realtime only invalidates TanStack Query; the marker is derived from the
 * authoritative replacement response rather than from an ephemeral socket event.
 * See `dev/development-plan/06-phase-2-content.md` (published-content replacement).
 */
export function usePublishedContentReplacement(
  resourceKey: string | undefined,
  revisionId: string | undefined,
): boolean {
  const [observed, setObserved] = useState<{
    resourceKey: string | undefined
    revisionId: string | undefined
    wasReplaced: boolean
  }>({ resourceKey, revisionId, wasReplaced: false })

  if (observed.resourceKey !== resourceKey) {
    // React's guarded render-time adjustment makes the reset synchronous: a
    // mounted route never paints the previous resource's marker for one frame.
    setObserved({ resourceKey, revisionId, wasReplaced: false })
    return false
  }
  if (observed.revisionId !== revisionId) {
    const wasReplaced = observed.revisionId !== undefined && revisionId !== undefined
    setObserved({ resourceKey, revisionId, wasReplaced })
    return wasReplaced
  }

  return observed.wasReplaced
}
